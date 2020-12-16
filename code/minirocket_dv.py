# Angus Dempster, Daniel F Schmidt, Geoffrey I Webb

# MiniRocket: A Very Fast (Almost) Deterministic Transform for Time Series
# Classification

# arXiv:???

from numba import njit
import numpy as np

from minirocket import _PPV, _fit_dilations, _quantiles

@njit("Tuple((float32[:],float32[:,:]))(float32[:,:],int32[:],int32[:],float32[:])", fastmath = True, parallel = False)
def _fit_biases_transform(X, dilations, num_features_per_dilation, quantiles):

    num_examples, input_length = X.shape

    # equivalent to:
    # >>> from itertools import combinations
    # >>> indices = np.array([_ for _ in combinations(np.arange(9), 3)], dtype = np.int32)
    indices = np.array((
        0,1,2,0,1,3,0,1,4,0,1,5,0,1,6,0,1,7,0,1,8,
        0,2,3,0,2,4,0,2,5,0,2,6,0,2,7,0,2,8,0,3,4,
        0,3,5,0,3,6,0,3,7,0,3,8,0,4,5,0,4,6,0,4,7,
        0,4,8,0,5,6,0,5,7,0,5,8,0,6,7,0,6,8,0,7,8,
        1,2,3,1,2,4,1,2,5,1,2,6,1,2,7,1,2,8,1,3,4,
        1,3,5,1,3,6,1,3,7,1,3,8,1,4,5,1,4,6,1,4,7,
        1,4,8,1,5,6,1,5,7,1,5,8,1,6,7,1,6,8,1,7,8,
        2,3,4,2,3,5,2,3,6,2,3,7,2,3,8,2,4,5,2,4,6,
        2,4,7,2,4,8,2,5,6,2,5,7,2,5,8,2,6,7,2,6,8,
        2,7,8,3,4,5,3,4,6,3,4,7,3,4,8,3,5,6,3,5,7,
        3,5,8,3,6,7,3,6,8,3,7,8,4,5,6,4,5,7,4,5,8,
        4,6,7,4,6,8,4,7,8,5,6,7,5,6,8,5,7,8,6,7,8
    ), dtype = np.int32).reshape(84, 3)

    num_kernels = len(indices)
    num_dilations = len(dilations)

    num_features = num_kernels * np.sum(num_features_per_dilation)

    biases = np.zeros(num_features, dtype = np.float32)

    features = np.zeros((num_examples, num_features), dtype = np.float32)

    feature_index_start = 0

    for dilation_index in range(num_dilations):

        _padding0 = dilation_index % 2

        dilation = dilations[dilation_index]
        padding = ((9 - 1) * dilation) // 2

        num_features_this_dilation = num_features_per_dilation[dilation_index]

        for kernel_index in range(num_kernels):

            feature_index_end = feature_index_start + num_features_this_dilation

            _padding1 = (_padding0 + kernel_index) % 2

            index_0, index_1, index_2 = indices[kernel_index]

            C = np.zeros((num_examples, input_length), dtype = np.float32)

            for example_index in range(num_examples):

                _X = X[example_index]

                A = -_X          # A = alpha * X = -X
                G = _X + _X + _X # G = gamma * X = 3X

                C_alpha = np.zeros(input_length, dtype = np.float32)
                C_alpha[:] = A

                C_gamma = np.zeros((9, input_length), dtype = np.float32)
                C_gamma[9 // 2] = G

                start = dilation
                end = input_length - padding

                for gamma_index in range(9 // 2):

                    C_alpha[-end:] = C_alpha[-end:] + A[:end]
                    C_gamma[gamma_index, -end:] = G[:end]

                    end += dilation

                for gamma_index in range(9 // 2 + 1, 9):

                    C_alpha[:-start] = C_alpha[:-start] + A[start:]
                    C_gamma[gamma_index, :-start] = G[start:]

                    start += dilation

                C[example_index] = C_alpha + C_gamma[index_0] + C_gamma[index_1] + C_gamma[index_2]

            biases[feature_index_start:feature_index_end] = np.quantile(C, quantiles[feature_index_start:feature_index_end])

            for example_index in range(num_examples):
                if _padding1 == 0:
                    for feature_count in range(num_features_this_dilation):
                        features[example_index, feature_index_start + feature_count] = _PPV(C[example_index], biases[feature_index_start + feature_count]).mean()
                else:
                    for feature_count in range(num_features_this_dilation):
                        features[example_index, feature_index_start + feature_count] = _PPV(C[example_index][padding:-padding], biases[feature_index_start + feature_count]).mean()

            feature_index_start = feature_index_end

    return biases, features

def fit_transform(X, num_features = 10_000, max_dilations_per_kernel = 32):

    _, input_length = X.shape

    num_kernels = 84

    dilations, num_features_per_dilation = _fit_dilations(input_length, num_features, max_dilations_per_kernel)

    num_features_per_kernel = np.sum(num_features_per_dilation)

    quantiles = _quantiles(num_kernels * num_features_per_kernel)

    biases, features = _fit_biases_transform(X, dilations, num_features_per_dilation, quantiles)

    return (dilations, num_features_per_dilation, biases), features
