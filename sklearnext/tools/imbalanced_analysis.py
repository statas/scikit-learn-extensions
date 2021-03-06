"""
The :mod:`sklearnext.tools.imbalanced_analysis` module
contains functions to evaluate the results of model search.
"""

# Author: Georgios Douzas <gdouzas@icloud.com>
# Licence: MIT

from itertools import product
from os.path import join
from os import listdir
from re import match, sub
import numpy as np
import pandas as pd
from scipy.stats import friedmanchisquare
from sklearn.model_selection import StratifiedKFold
from ..utils import check_datasets, check_oversamplers_classifiers
from ..metrics import SCORERS
from ..model_selection import ModelSearchCV


def read_csv_dir(dirpath):
    "Reads a directory of csv files and returns a dictionary of dataset-name:(X,y) pairs."
    datasets = []
    csv_files = [csv_file for csv_file in listdir(dirpath) if match('^.+\.csv$', csv_file)]
    for csv_file in csv_files:
        dataset = pd.read_csv(join(dirpath, csv_file))
        X, y = dataset.iloc[:, :-1], dataset.iloc[:, -1]
        dataset_name = sub(".csv", "", csv_file)
        datasets.append((dataset_name, (X, y)))
    return datasets


def summarize_datasets(datasets):
    """Creates a summary of the datasets."""
    datasets = check_datasets(datasets)
    summary_columns = ["Dataset name",
                       "# of features",
                       "# of instances",
                       "# of minority instances",
                       "# of majority instances",
                       "Imbalance Ratio"]
    datasets_summary = pd.DataFrame({}, columns=summary_columns)
    for dataset_name, (X, y) in datasets:
        n_instances = ((y == 0).sum(), (y == 1).sum())
        dataset_summary = pd.DataFrame([[dataset_name,
                                         X.shape[1],
                                         y.size,
                                         n_instances[1],
                                         n_instances[0],
                                         round(n_instances[0] / n_instances[1], 2)]],
                                       columns=datasets_summary.columns)
        datasets_summary = datasets_summary.append(dataset_summary, ignore_index=True)
    datasets_summary[datasets_summary.columns[1:-1]] = datasets_summary[datasets_summary.columns[1:-1]].astype(int)
    return datasets_summary


def _calculate_stats(experiment):
    """Calculates stats for positive and negative scorers."""
    grouped_results = experiment.results_.groupby(experiment.results_.columns[:-1].tolist(), as_index=False)
    stats = grouped_results.agg({'CV score': [np.mean, np.std]})
    stats.columns = experiment.results_.columns.tolist()[:-1] + ['Mean CV score', 'Std CV score']
    return stats


def calculate_stats(experiment):
    """Calculates mean and standard deviation across experiments for every
    combination of datasets, classifiers, oversamplers and metrics."""
    stats = _calculate_stats(experiment)
    stats['Mean CV score'] = np.abs(stats['Mean CV score'])
    return stats


def calculate_optimal_stats(experiment, return_optimal_params=False):
    """Calculates the highest mean and standard deviation for every
    combination of classifiers and oversamplers across different
    hyperparameters' configurations."""

    # Classifiers names
    clfs_names = [clf_name for clf_name, *_ in experiment.classifiers]
    expanded_clfs_names = [clf_name for clf_name, _ in experiment.classifiers_]

    # Oversamplers names
    oversamplers_names = [oversampler_name for oversampler_name, *_ in experiment.oversamplers]
    expanded_oversamplers_names = [oversampler_name for oversampler_name, _ in experiment.oversamplers_]

    # Oversamplers
    oversamplers = [(oversampler_name, oversampler) for oversampler_name, oversampler, *_ in experiment.oversamplers]

    # Calculate stats table
    stats = _calculate_stats(experiment)
    optimal_stats = pd.DataFrame(columns=stats.columns)

    # Populate optimal stats table
    for dataset_name, clf_name, oversampler_name in product(experiment.datasets_names_, clfs_names, oversamplers_names):
        matched_clfs_names = [exp_clf_name for exp_clf_name in expanded_clfs_names if match(clf_name, exp_clf_name)]
        matched_oversamplers_names = [exp_oversampler_name for exp_oversampler_name in expanded_oversamplers_names if
                                      match(oversampler_name, exp_oversampler_name)]

        is_matched_clfs = np.isin(stats['Classifier'], matched_clfs_names)
        is_matched_oversamplers = np.isin(stats['Oversampler'], matched_oversamplers_names)
        is_matched_dataset = (stats['Dataset'] == dataset_name)

        matched_stats = stats[is_matched_clfs & is_matched_oversamplers & is_matched_dataset]
        optimal_matched_stats = matched_stats.groupby('Metric', as_index=False).agg(
            {'Mean CV score': [max, lambda col: matched_stats['Std CV score'][np.argmax(col)]]})

        if not return_optimal_params:
            optimal_matched_names = pd.DataFrame([[dataset_name, clf_name, oversampler_name]] * len(experiment.scoring),
                                                 columns=stats.columns[:-3])
        else:
            optimal_matched_names = matched_stats.groupby('Metric').agg(
                {'Mean CV score': {'Classifier': lambda col: matched_stats['Classifier'][np.argmax(col)],
                                   'Oversampler': lambda col: matched_stats['Oversampler'][np.argmax(col)]}})
            optimal_matched_names.columns = optimal_matched_names.columns.get_level_values(1)
            optimal_matched_names['Dataset'] = dataset_name
            optimal_matched_names['Classifier'] = optimal_matched_names['Classifier'].apply(
                lambda exp_clf_name: (clf_name, dict(experiment.classifiers_)[exp_clf_name].get_params()))
            if dict(oversamplers)[oversampler_name] is None:
                optimal_matched_names['Oversampler'] = optimal_matched_names['Oversampler'].apply(
                    lambda exp_oversampler_name: (oversampler_name, None))
            else:
                optimal_matched_names['Oversampler'] = optimal_matched_names['Oversampler'].apply(
                    lambda exp_oversampler_name: (
                    oversampler_name, dict(experiment.oversamplers_)[exp_oversampler_name].get_params()))
            optimal_matched_names = optimal_matched_names.reset_index()[stats.columns[:-3]]

        optimal_matched_stats.columns = stats.columns[-3:]
        optimal_matched_stats = pd.concat([optimal_matched_names, optimal_matched_stats], axis=1)
        optimal_stats = optimal_stats.append(optimal_matched_stats, ignore_index=True)

    optimal_stats['Mean CV score'] = np.abs(optimal_stats['Mean CV score'])
    return optimal_stats


def calculate_optimal_stats_wide(experiment, append_std=True):
    """Calculates in wide format the highest mean and standard
    deviation for every combination of classfiers and oversamplers
    across different hyperparameters' configurations."""
    optimal_stats = calculate_optimal_stats(experiment)

    # Calculate wide format of mean cv
    optimal_mean_wide = optimal_stats.pivot_table(index=['Dataset', 'Classifier', 'Metric'], columns=['Oversampler'],
                                                  values='Mean CV score').reset_index()
    optimal_mean_wide.columns.rename(None, inplace=True)

    # Calculate wide format of std cv
    if append_std:
        optimal_std_wide = optimal_stats.pivot_table(index=['Dataset', 'Classifier', 'Metric'], columns=['Oversampler'],
                                                     values='Std CV score').reset_index()
        optimal_std_wide.columns.rename(None, inplace=True)

    # Populate wide format of optimal stats
    oversamplers_names = [oversampler_name for oversampler_name, *_ in experiment.oversamplers]
    optimal_stats_wide = optimal_mean_wide
    if append_std:
        for oversampler_name in oversamplers_names:
            optimal_stats_wide[oversampler_name] = list(
                zip(optimal_stats_wide[oversampler_name], optimal_std_wide[oversampler_name]))
    return optimal_stats_wide


def _return_row_ranking(row, sign):
    """Returns the ranking of mean cv scores for
    a row of an array. In case of tie, each value
    is replaced with its group average."""
    ranking = (sign * row).argsort().argsort().astype(float)
    groups = np.unique(row, return_inverse=True)[1]
    for group_label in np.unique(groups):
        indices = (groups == group_label)
        ranking[indices] = ranking[indices].mean()
    return ranking.size - ranking


def calculate_ranking(experiment):
    """Calculates the ranking of oversamplers."""
    optimal_stats_wide = calculate_optimal_stats_wide(experiment, append_std=False)
    ranking = optimal_stats_wide.apply(lambda row: _return_row_ranking(row[3:], SCORERS[row[2]]._sign), axis=1)
    return pd.concat([optimal_stats_wide.iloc[:, :3], ranking], axis=1)


def calculate_mean_ranking(experiment):
    """Calculates the ranking of oversamplers."""
    ranking = calculate_ranking(experiment)
    return ranking.groupby(['Classifier', 'Metric'], as_index=False).mean()


def calculate_friedman_test(experiment, alpha=0.05):
    """Calculates the friedman test across datasets for every
    combination of classifiers and metrics."""
    if len(experiment.oversamplers_) < 3:
        raise ValueError('Friedman test can not be applied. More than two oversampling methods are needed.')
    ranking = calculate_ranking(experiment)
    extract_pvalue = lambda df: friedmanchisquare(*df.iloc[:, 3:].transpose().values.tolist()).pvalue
    friedman_test_results = ranking.groupby(['Classifier', 'Metric']).apply(extract_pvalue).reset_index().rename(
        columns={0: 'p-value'})
    friedman_test_results['Significance'] = friedman_test_results['p-value'] < alpha
    return friedman_test_results


def evaluate_imbalanced_experiment(X, y, oversamplers, classifiers, scoring=None,
                                   n_splits=3, n_runs=3, random_state=None, n_jobs=-1):
    n_datasets = len(X) if not hasattr(X, 'shape') else 1
    estimators, param_grids = check_oversamplers_classifiers(oversamplers, classifiers, n_runs, random_state, n_datasets).values()
    mscv = ModelSearchCV(estimators,
                         param_grids,
                         scoring=scoring,
                         iid=True,
                         refit=False,
                         cv=StratifiedKFold(n_splits=n_splits, shuffle=True,random_state=random_state),
                         error_score='raise',
                         return_train_score=False,
                         scheduler=None,
                         n_jobs=n_jobs,
                         cache_cv=True)
    mscv.fit(X, y)
    return mscv
