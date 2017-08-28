from itertools import product
from sklearn.utils import check_X_y, check_random_state


def _flatten_parameters_list(parameters_list):
    """Flattens a dictionaries' list of parameters."""
    flat_parameters = []
    for parameters_dict in parameters_list:
        flat_parameters += [dict(zip(parameters_dict.keys(), parameter_product)) for parameter_product in product(*parameters_dict.values())]
    return flat_parameters

def check_datasets(datasets):
    """Checks that datasets is a list of (X,y) pairs or a dictionary of dataset-name:(X,y) pairs."""
    if isinstance(datasets, list):
        return {("dataset_" + str(ind + 1)):check_X_y(*dataset) for ind, dataset in enumerate(datasets)} 
    elif isinstance(datasets, dict):
        datasets_names = datasets.keys()
        are_all_strings = all([isinstance(dataset_name, str) for dataset_name in datasets_names])
        are_unique = len(list(datasets_names)) == len(set(datasets_names))
        if not are_all_strings or not are_unique:
            raise ValueError("The names of the datasets should be unique strings.")
        return {dataset_name:check_X_y(*dataset) for dataset_name, dataset in datasets.items()}
    else:
        raise ValueError("The datasets should be a list of (X,y) pairs or a dictionary of dataset-name:(X,y) pairs.")

def check_random_states(random_state, repetitions):
    """Create random states for experiments."""
    return [check_random_state(random_state).randint(0, 2 ** 32 - 1) for ind in range(repetitions)]

def check_classifiers(classifiers):
    return classifiers

def check_oversamplers(oversampling_methods):
    return oversampling_methods