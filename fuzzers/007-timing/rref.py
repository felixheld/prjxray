#!/usr/bin/env python3

from timfuz import Benchmark, Ar_di2np, loadc_Ads_b, index_names, A_ds2np, simplify_rows, OrderedSet
import numpy as np
import glob
import math
import json
import sympy
from collections import OrderedDict
from fractions import Fraction


def rm_zero_cols(Ads, verbose=True):
    removed = OrderedSet()

    print('Removing ZERO elements')
    for row_ds in Ads:
        for k in set(row_ds.keys()):
            if k in removed:
                del row_ds[k]
            elif k.find('ZERO') >= 0:
                del row_ds[k]
                removed.add(k)
                if verbose:
                    print('  Removing %s' % k)
    return removed


def fracr_quick(r):
    return [Fraction(numerator=int(x), denominator=1) for x in r]


def fracm_quick(m):
    '''Convert integer matrix to Fraction matrix'''
    t = type(m[0][0])
    print('fracm_quick type: %s' % t)
    return [fracr_quick(r) for r in m]


class State(object):
    def __init__(self, Ads, zero_names=[]):
        self.Ads = Ads
        self.names = index_names(self.Ads)

        # known zero delay elements
        self.zero_names = OrderedSet(zero_names)
        # active names in rows
        # includes sub variables, excludes variables that have been substituted out
        self.base_names = OrderedSet(self.names)
        #self.names = OrderedSet(self.base_names)
        self.names = set(self.base_names)
        # List of variable substitutions
        # k => dict of v:n entries that it came from
        self.subs = OrderedDict()
        self.verbose = True

    def print_stats(self):
        print("Stats")
        print("  Substitutions: %u" % len(self.subs))
        if self.subs:
            print(
                "    Largest: %u" % max([len(x) for x in self.subs.values()]))
        print("  Rows: %u" % len(self.Ads))
        print(
            "  Cols (in): %u" % (len(self.base_names) + len(self.zero_names)))
        print("  Cols (preprocessed): %u" % len(self.base_names))
        print("    ZERO names: %u" % len(self.zero_names))
        print("  Cols (out): %u" % len(self.names))
        print("  Solvable vars: %u" % len(self.names & self.base_names))
        assert len(self.names) >= len(self.subs)

    @staticmethod
    def load(fn_ins, simplify=False, corner=None, rm_zero=False):
        zero_names = OrderedSet()

        Ads, b = loadc_Ads_b(fn_ins, corner=corner)
        if rm_zero:
            zero_names = rm_zero_cols(Ads)
        if simplify:
            print('Simplifying corner %s' % (corner, ))
            Ads, b = simplify_rows(Ads, b, remove_zd=False, corner=corner)
        return State(Ads, zero_names=zero_names)


def write_state(state, fout):
    j = {
        'names':
        OrderedDict([(x, None) for x in state.names]),
        'zero_names':
        sorted(list(state.zero_names)),
        'base_names':
        sorted(list(state.base_names)),
        'subs':
        OrderedDict([(name, values) for name, values in state.subs.items()]),
        'pivots':
        state.pivots,
    }
    json.dump(j, fout, sort_keys=True, indent=4, separators=(',', ': '))


def row_np2ds(rownp, names):
    ret = OrderedDict()
    assert len(rownp) == len(names), (len(rownp), len(names))
    for namei, name in enumerate(names):
        v = rownp[namei]
        if v:
            ret[name] = v
    return ret


def row_sym2dsf(rowsym, names):
    '''Convert a sympy row into a dictionary of keys to (numerator, denominator) tuples'''
    from sympy import fraction

    ret = OrderedDict()
    assert len(rowsym) == len(names), (len(rowsym), len(names))
    for namei, name in enumerate(names):
        v = rowsym[namei]
        if v:
            (num, den) = fraction(v)
            ret[name] = (int(num), int(den))
    return ret


def state_rref(state, verbose=False):
    print('Converting rows to integer keys')
    names, Anp = A_ds2np(state.Ads)

    print('np: %u rows x %u cols' % (len(Anp), len(Anp[0])))
    mnp = Anp
    print('Matrix: %u rows x %u cols' % (len(mnp), len(mnp[0])))
    print('Converting np to sympy matrix')
    mfrac = fracm_quick(mnp)
    # doesn't seem to change anything
    #msym = sympy.MutableSparseMatrix(mfrac)
    msym = sympy.Matrix(mfrac)
    # internal encoding has significnat performance implications
    #assert type(msym[0]) is sympy.Integer

    if verbose:
        print('names')
        print(names)
        print('Matrix')
        sympy.pprint(msym)
    print('Making rref')
    rref, pivots = msym.rref(normalize_last=False)

    if verbose:
        print('Pivots')
        sympy.pprint(pivots)
        print('rref')
        sympy.pprint(rref)

    state.pivots = OrderedDict()

    def row_solved(rowsym, row_pivot):
        for ci, c in enumerate(rowsym):
            if ci == row_pivot:
                continue
            if c != 0:
                return False
        return True

    #rrefnp = np.array(rref).astype(np.float64)
    #print('Computing groups w/ rref %u row x %u col' % (len(rrefnp), len(rrefnp[0])))
    #print(rrefnp)
    # rows that have a single 1 are okay
    # anything else requires substitution (unless all 0)
    # pivots may be fewer than the rows
    # remaining rows should be 0s
    for row_i, row_pivot in enumerate(pivots):
        rowsym = rref.row(row_i)
        # yipee! nothign to report
        if row_solved(rowsym, row_pivot):
            continue

        # a grouping
        group_name = "GRP_%u" % row_i
        rowdsf = row_sym2dsf(rowsym, names)

        state.subs[group_name] = rowdsf
        # Add the new variables
        state.names.add(group_name)
        # Remove substituted variables
        # Note: variables may appear multiple times
        state.names.difference_update(OrderedSet(rowdsf.keys()))
        pivot_name = names[row_pivot]
        state.pivots[group_name] = pivot_name
        if verbose:
            print("%s (%s): %s" % (group_name, pivot_name, rowdsf))

    return state


def run(fnout, fn_ins, simplify=False, corner=None, rm_zero=False, verbose=0):
    print('Loading data')

    assert len(fn_ins) > 0
    state = State.load(
        fn_ins, simplify=simplify, corner=corner, rm_zero=rm_zero)
    state_rref(state, verbose=verbose)
    state.print_stats()
    if fnout:
        with open(fnout, 'w') as fout:
            write_state(state, fout)


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description=
        'Compute reduced row echelon (RREF) to form sub.json (variable groups)'
    )

    parser.add_argument('--verbose', action='store_true', help='')
    parser.add_argument('--simplify', action='store_true', help='')
    parser.add_argument('--corner', default="slow_max", help='')
    parser.add_argument(
        '--rm-zero', action='store_true', help='Remove ZERO elements')
    parser.add_argument(
        '--speed-json',
        default='build_speed/speed.json',
        help='Provides speed index to name translation')
    parser.add_argument('--out', help='Output sub.json substitution result')
    parser.add_argument('fns_in', nargs='*', help='timing4i.csv input files')
    args = parser.parse_args()
    bench = Benchmark()

    fns_in = args.fns_in
    if not fns_in:
        fns_in = glob.glob('specimen_*/timing4i.csv')

    try:
        run(
            fnout=args.out,
            fn_ins=fns_in,
            simplify=args.simplify,
            corner=args.corner,
            rm_zero=args.rm_zero,
            verbose=args.verbose)
    finally:
        print('Exiting after %s' % bench)


if __name__ == '__main__':
    main()
