#include "monte_carlo.h"
#include <algorithm>
#include <cmath>
#include <cstring>
#include <numeric>
#include <random>
#include <stdexcept>
#include <vector>

namespace {
void require(bool ok, const char* message) {
    if (!ok) throw std::invalid_argument(message);
}
double quantile(const std::vector<double>& a, double p) {
    const double index = p * static_cast<double>(a.size()-1);
    const auto lo = static_cast<std::size_t>(index);
    const auto hi = std::min(lo+1, a.size()-1);
    return a[lo] + (index-static_cast<double>(lo))*(a[hi]-a[lo]);
}
class Normal {
    std::mt19937_64 engine;
    bool cached = false;
    double spare = 0;
    double uniform() {
        return (static_cast<double>(engine() >> 11)+0.5)/9007199254740992.0;
    }
public:
    explicit Normal(std::uint64_t seed) : engine(seed) {}
    double next() {
        if (cached) { cached=false; return spare; }
        const double radius=std::sqrt(-2*std::log(uniform()));
        const double angle=6.2831853071795864769*uniform();
        spare=radius*std::sin(angle);
        cached=true;
        return radius*std::cos(angle);
    }
};
std::vector<double> factor(int n, const double* c) {
    double scale=0;
    for (int i=0;i<n*n;++i) {
        require(std::isfinite(c[i]),"Covariance must be finite");
        scale=std::max(scale,std::abs(c[i]));
    }
    const double tolerance=std::max(1e-14,scale*1e-10);
    for (int i=0;i<n;++i) {
        require(c[i*n+i]>=0 && c[i*n+i]<=25,"Invalid annual variance");
        for (int j=0;j<n;++j)
            require(std::abs(c[i*n+j]-c[j*n+i])<=tolerance,"Asymmetric covariance");
    }
    std::vector<double> l(static_cast<std::size_t>(n*n),0);
    for (int i=0;i<n;++i) for (int j=0;j<=i;++j) {
        double r=c[i*n+j];
        for (int k=0;k<j;++k) r-=l[i*n+k]*l[j*n+k];
        if (i==j) {
            require(r>=-tolerance,"Covariance is not positive semidefinite");
            l[i*n+j]=std::sqrt(std::max(0.0,r));
        } else if (l[j*n+j]>0) {
            l[i*n+j]=r/l[j*n+j];
        } else {
            require(std::abs(r)<=tolerance,"Invalid singular covariance");
        }
    }
    return l;
}
void run(int n,const double* e,const double* mu,const double* cov,
         int days,int sims,std::uint64_t seed,double confidence,int points,
         double* out,std::uint64_t size) {
    require(n>=1 && n<=20 && e && mu && cov && out,"Invalid asset inputs");
    require(days>=1 && days<=1260 && sims>=1000 && sims<=50000,"Invalid horizon or path count");
    require(points>=2 && points<=65 && points<=days+1,"Invalid checkpoints");
    require(std::isfinite(confidence) && confidence>=.9 && confidence<=.99,"Invalid confidence");
    require(static_cast<std::uint64_t>(n)*n*days*sims<=1000000000ULL,
            "Work limit exceeded; reduce paths or horizon");
    require(size>=static_cast<std::uint64_t>(5+15*points+sims),"Output buffer too small");
    double nav=0;
    for (int i=0;i<n;++i) {
        require(std::isfinite(e[i]) && e[i]>=0 && e[i]<=1e15,"Invalid exposure");
        require(std::isfinite(mu[i]) && std::abs(mu[i])<=.5,"Invalid assumed drift");
        nav+=e[i];
    }
    require(nav>0,"Positive portfolio value required");
    const auto l=factor(n,cov);
    std::vector<std::vector<double>> checkpoints(
        static_cast<std::size_t>(points),std::vector<double>(static_cast<std::size_t>(sims)));
    std::vector<double> values(static_cast<std::size_t>(n)),z(static_cast<std::size_t>(n));
    Normal normal(seed);
    const double root_dt=std::sqrt(1.0/252);
    for (int path=0;path<sims;++path) {
        std::copy(e,e+n,values.begin());
        checkpoints[0][path]=nav;
        int checkpoint=1;
        for (int day=1;day<=days;++day) {
            for (auto& v:z) v=normal.next();
            for (int i=0;i<n;++i) {
                double shock=0;
                for (int j=0;j<=i;++j) shock+=l[i*n+j]*z[j];
                values[i]*=std::exp((mu[i]-.5*cov[i*n+i])/252+root_dt*shock);
                require(std::isfinite(values[i]),"Non-finite simulated value");
            }
            if (checkpoint<points && day==checkpoint*days/(points-1)) {
                checkpoints[checkpoint][path]=std::accumulate(values.begin(),values.end(),0.0);
                ++checkpoint;
            }
        }
    }
    for (int p=0;p<12;++p) for (int k=0;k<points;++k)
        out[5+3*points+p*points+k]=checkpoints[k][p];
    std::size_t offset=5;
    for (auto& sample:checkpoints) {
        std::sort(sample.begin(),sample.end());
        for (double q:{.05,.5,.95}) out[offset++]=quantile(sample,q);
    }
    const auto& terminal=checkpoints.back();
    out[0]=static_cast<double>(std::lower_bound(terminal.begin(),terminal.end(),nav)
                              -terminal.begin())/sims;
    out[1]=nav-quantile(terminal,1-confidence);
    // Exactly alpha of empirical probability mass, including fractional boundary.
    const double count=(1-confidence)*sims;
    const auto whole=static_cast<std::size_t>(count);
    double tail_loss=0;
    for (std::size_t i=0;i<whole;++i) tail_loss+=nav-terminal[i];
    if (whole<terminal.size())
        tail_loss+=(count-static_cast<double>(whole))*(nav-terminal[whole]);
    out[2]=tail_loss/count;
    out[3]=std::accumulate(terminal.begin(),terminal.end(),0.0)/sims;
    out[4]=nav;
    std::copy(terminal.begin(),terminal.end(),out+5+15*points);
}
}
extern "C" int qmc_abi_version() noexcept { return 1; }
extern "C" int qmc_simulate(
    int n,const double* e,const double* mu,const double* c,
    int days,int sims,std::uint64_t seed,double confidence,int points,
    double* out,std::uint64_t size,char* error,int error_size) noexcept {
    try {
        run(n,e,mu,c,days,sims,seed,confidence,points,out,size);
        return 0;
    } catch (const std::exception& exception) {
        if (error && error_size>0) {
            const auto len=std::min(std::strlen(exception.what()),static_cast<std::size_t>(error_size-1));
            std::memcpy(error,exception.what(),len); error[len]='\0';
        }
        return 1;
    } catch (...) { return 2; }
}
