#include "monte_carlo.h"
#include <cmath>
#include <iostream>
#include <stdexcept>
#include <vector>
void check(bool ok,const char* message) { if (!ok) throw std::runtime_error(message); }
std::vector<double> simulate(std::vector<double> e,std::vector<double> c,double drift=0) {
    const auto n=static_cast<int>(e.size());
    std::vector<double> mu(e.size(),drift),out(5+15*13+20000);
    char error[256]={};
    check(qmc_simulate(n,e.data(),mu.data(),c.data(),252,20000,42,.95,13,
                      out.data(),out.size(),error,256)==0,error);
    return out;
}
int main() {
    try {
        const auto cash=simulate({100000},{0});
        check(cash[0]==0 && cash[1]==0 && cash[2]==0 && cash[3]==100000,
              "Zero-volatility cash must stay constant");
        const auto a=simulate({100000},{.04});
        check(a==simulate({100000},{.04}),"Seed must reproduce all output");
        const double q=100000*std::exp(-.02-.2*1.6448536269514722);
        const double es=100000-100000*.5*std::erfc((1.6448536269514722+.2)/std::sqrt(2))/.05;
        check(std::abs(a[1]-(100000-q))<800,"VaR disagrees with lognormal reference");
        check(std::abs(a[2]-es)<900 && a[2]>=a[1],"ES disagrees with reference");
        check(std::abs(a[3]-100000)<700,"Mean disagrees with zero-drift expectation");
        const auto independent=simulate({50000,50000},{.04,0,0,.04});
        const auto identical=simulate({50000,50000},{.04,.04,.04,.04});
        check(independent[1]<identical[1],"Independent assets should diversify");
        check(std::abs(identical[1]-a[1])<900,"Singular perfect correlation must work");
    } catch (const std::exception& e) { std::cerr<<e.what()<<'\n';return 1; }
    std::cout<<"Native Monte Carlo checks passed\n";
}
