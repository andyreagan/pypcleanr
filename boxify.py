import re
import click
from pathlib import Path
from typing import Optional
import random

known_namespaces = {
    'dplyr': {'distinct', 'pull', 'arrange', 'summarise', 'select', 'mutate_at', 'group_by', 'mutate', 'filter', 'sym', 'bind_rows'},
    'glue': {'glue'},
    'tidyr': {'pivot_wider', 'pivot_longer', 'spread'}
}
R_output = map(lambda x: x.split(','), Path('all_names.csv').read_text().strip().split('\n')[1:])


def printq(_, quiet=True):
    if not quiet:
        print(_)


def boxify(raw_script: str, max_explicit=10, quiet=False):
    '''Assume that box is not in use already, everything is either global or namespaced to start.'''
    all_function_calls = re.findall('([A-Za-z0-9_]+?)\(.*?\)', raw_script)
    explicitly_namespaced = re.findall('([A-Za-z0-9_]+?)::([A-Za-z0-9_]+?)\(.*?\)', raw_script)
    libraries_loaded = re.findall('library\(([A-Za-z0-9_]+?)\)', raw_script)
    known_namespaces = dict()
    for package, function in R_output:
        # filter all R packages to those that are attached by the script
        # if package in libraries_loaded:
        if True:
            # can do the following bit in one line
            # if package not in known_namespaces:
            #     known_namespaces[package] = set()
            # known_namespaces[package] = known_namespaces[package] | {function}
            known_namespaces[package] = known_namespaces.get(package, set()) | {function}

    # add these function to the top of the library search list, and to the function list
    for nonstandard_fun, lib, escaped in (('%>%', 'magrittr', '`%>%`'), ('%T>%', 'magrittr', '`%T>%`'), ('%<>%', 'magrittr', '`%<>%`')):
        # magrittr = len(re.findall('%>%', raw_script)) > 0
        found = len(re.findall(nonstandard_fun, raw_script)) > 0
        libraries_loaded = [lib] + list(libraries_loaded)
        all_function_calls = list(all_function_calls) + [nonstandard_fun]


    namespaced = dict()
    by_function = dict()
    for k, v in explicitly_namespaced:
        namespaced[k] = namespaced.get(k, set()) | {v}
        by_function[v] = namespaced.get(v, set()) | {k}
    for k, v in by_function.items():
        if len(v) > 1:
            printq(f'function {k} loaded explicitly from multiple packages {v}...we will import from both', quiet=quiet)

    # ordered list of namespaces to use when multiple
    ranked_namespaces = libraries_loaded + ['base', 'dplyr', 'magrittr', 'tidyr']
    for function in all_function_calls:
        # if function in explicitly_namespaced.values():
        if function in by_function:
            printq(f'{function=} used an explicit namespace somewhere in the script, rely on that one(s) {by_function[function]}', quiet=quiet)
        # would allow duplicate loads from every library that exports it:
        # for namespace, functions in known_namespaces.items():
        #     if function in functions:
        #         namespaced[namespace] = namespaced.get(namespace, set()) | {function}
        namespaces = [namespace for namespace, functions in known_namespaces.items() if function in functions]
        if len(namespaces) > 1:
            printq(f"you use a function available in multiple namespaces: {function=} is found in {namespaces=}. using ranked list to select on (libraries loaded in order, then dplyr, magrittr)", quiet=quiet)
            ranked = [namespace for namespace in ranked_namespaces if namespace in namespaces]
            if len(ranked) > 1:
                printq(f"found multiple in {ranked=}, choosing the first one: {ranked[0]}", quiet=quiet)
                namespace = ranked[0]
            elif len(ranked) == 1:
                printq(f"ranked list choose {ranked[0]}", quiet=quiet)
                namespace = ranked[0]
            else:
                namespace = random.choice(namespaces)
                printq(f"didn't find a ranked choice...choosing randomly: {namespace}", quiet=quiet)
            namespaced[namespace] = namespaced.get(namespace, set()) | {function}
        elif len(namespaces) == 1:
            namespace = namespaces[0]
            namespaced[namespace] = namespaced.get(namespace, set()) | {function}


    lines = re.sub(
        'library\(([A-Za-z0-9_]+?)\)',
        '',
        re.sub(
            '([A-Za-z0-9_]+?)::([A-Za-z0-9_]+?)(\(.*?\))',
            '\\2\\3',
            raw_script
        )
    ).split('\n')
    box_imports = []

    # Don't mess with the shebang, skip it if it exists
    if lines[0][0:2] == '#!':
        box_imports.append(lines[0])
        lines = lines[1:]

    box_imports.append('box::use(box[use])')
    # if 'here' in namespaced:
    #     namespaced['here'] = namespaced['here'] | {'here'}
    # else:
    #     namespaced['here'] = {'here'}
    for k, v in sorted(namespaced.items()):
        box_imports.append(f'use({k}[{", ".join(v)}])')

    # return all_function_calls, explicitly_namespaced, sorted(namespaced.items())
    return '\n'.join(box_imports + lines)


@click.command()
@click.argument('Rscript')
@click.option('--local-lib-dir')
@click.option('--quiet', is_flag=True)
def cli(rscript: str, local_lib_dir: Optional[str], quiet: Optional[bool]):
    print(boxify(Path(rscript).read_text(), quiet=quiet))


if __name__ == '__main__':
    cli()


# # box::use(box[use])
# all_packages = installed.packages()[, "Package"]
#
# # # paste(all_packages, collapse='|')
# # d = data.frame(package=all_packages, names=NA)
# # for (package in c('R6')) {
# #     library(package, character.only=T)
# #     name_df = data.frame(package=package, names_new=ls(glue("package:{package}")))
# #     d = select(mutate(left_join(d, name_df), names=coalesce(names, names_new)), -names_new)
# # }
#
# # d = dplyr::distinct(data.frame(package=all_packages, names=NA))
# d = head(data.frame(package=all_packages, names=""), 0)
# # for (package in c("tools", "utils", "survival")) {
# for (package in all_packages) {
#     # print(package)
#     if (package %in% c('box')) {
#         print(glue::glue("skipping... {package}"))
#     } else {
#         suppressPackageStartupMessages(library(package, character.only=T))
#         # use(dplyr[select, left_join, mutate, coalesce, distinct])
#         # use(glue[glue])
#         names_ls = ls(glue::glue("package:{package}"))
#         # print(names_ls)
#         if (length(names_ls) > 0) {
#             name_df = data.frame(package=package, names=names_ls)
#             # print(name_df)
#             # d = dplyr::select(
#             #     dplyr::mutate(
#             #         dplyr::left_join(
#             #             d,
#             #             dplyr::distinct(name_df),
#             #             by="package"
#             #         ),
#             #         names=dplyr::coalesce(names, names_new)
#             #     ),
#             #     -names_new
#             # )
#             d = dplyr::distinct(dplyr::bind_rows(d, dplyr::distinct(name_df)))
#             # testthat::expect_equal(nrow(d), nrow(dplyr::distinct(d)))
#         } else {
#             print(glue::glue('no exported names from {package}'))
#         }
#     }
# }
# readr::write_csv(d, 'all_names.csv')
#
# > d %>% group_by(names) %>% dplyr::mutate(n=n()) %>% filter(n>1) %>% arrange(-n) %>% distinct(names, n)
# # A tibble: 459 x 2
# # Groups:   names [459]
#    names          n
#    <chr>      <int>
#  1 %>%           16
#  2 show           9
#  3 matches        6
#  4 plot           6
#  5 contains       4
#  6 ends_with      4
#  7 everything     4
#  8 last_col       4
#  9 num_range      4
# 10 one_of         4
# # … with 449 more rows
#


# TODO
# - add the ability to specify a local stanard library
#    - look for functions there and load them (first set box working directory, without cli bit)
#    - make sure they're exported in the lib
# - escape things that need to be escaped
# - add ability to pull in things from source, excluding a local library
# - pull the pull list of R functions right from R via a subprocess

--unroll --local-lib=src/lib
this won't unroll things from src/lib
it will destroy source() statements from src/lib while loading the functions explicitly from there
