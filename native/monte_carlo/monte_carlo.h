#pragma once
#include <cstdint>
#ifdef _WIN32
#define QMC_API __declspec(dllexport)
#else
#define QMC_API __attribute__((visibility("default")))
#endif
// ABI v1: caller owns buffers. Exposures are base-currency amounts; covariance
// is annualized log-return covariance (row-major); drift is assumed arithmetic
// GBM drift. Checkpoint k = floor(k*days/(checkpoints-1)).
// Output: 5 summary values, 3*checkpoints (p05,p50,p95), 12*checkpoints paths,
// then all sorted terminal values. Summary: loss probability, signed VaR,
// fractional-tail ES, mean terminal, initial NAV.
extern "C" QMC_API int qmc_simulate(
    int assets, const double* exposures, const double* drift, const double* covariance,
    int days, int simulations, std::uint64_t seed, double confidence, int checkpoints,
    double* output, std::uint64_t output_size, char* error, int error_size) noexcept;
extern "C" QMC_API int qmc_abi_version() noexcept;
