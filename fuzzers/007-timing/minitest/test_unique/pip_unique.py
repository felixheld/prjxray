#!/usr/bin/env python3

import re


def gen_wires(fin):
    for l in fin:
        lj = {}
        l = l.strip()
        for kvs in l.split():
            name, value = kvs.split(':')
            lj[name] = value

        tile_type, xy, wname = re.match(
            r'(.*)_(X[0-9]*Y[0-9]*)/(.*)', lj['NAME']).groups()
        lj['tile_type'] = tile_type
        lj['xy'] = xy
        lj['wname'] = wname

        lj['l'] = l

        yield lj


def run(node_fin, verbose=0):
    refnodes = {}
    nodei = 0
    for nodei, anode in enumerate(gen_wires(node_fin)):

        def getk(anode):
            return anode['wname']
            return (anode['tile_type'], anode['wname'])

        if nodei % 100000 == 0:
            print('Check node %d, %u node types' % (nodei, len(refnodes)))
        # Existing node?
        try:
            refnode = refnodes[getk(anode)]
        except KeyError:
            # Set as reference
            refnodes[getk(anode)] = anode
            continue
        k_invariant = (
            'CAN_INVERT',
            'IS_BUFFERED_2_0',
            'IS_BUFFERED_2_1',
            'IS_DIRECTIONAL',
            'IS_EXCLUDED_PIP',
            'IS_FIXED_INVERSION',
            'IS_INVERTED',
            'IS_PSEUDO',
            'IS_SITE_PIP',
            'IS_TEST_PIP',
        )
        k_varies = ('TILE', )
        # Verify equivilence
        for k in k_invariant:
            if k in refnode and k in anode:

                def fail():
                    print('Mismatch on %s' % k)
                    print(refnode[k], anode[k])
                    print(refnode['l'])
                    print(anode['l'])
                    #assert 0

                if refnode[k] != anode[k]:
                    print('')
                    fail()
            # A key in one but not the other?
            elif k in refnode or k in anode:
                assert 0
            elif k not in k_varies:
                assert 0


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(
        description=
        'Determines which info is consistent across PIPs with the same name')

    parser.add_argument('--verbose', type=int, help='')
    parser.add_argument(
        'node_fn_in',
        default='specimen_001/pip_all.txt',
        nargs='?',
        help='Input file')
    args = parser.parse_args()
    run(open(args.node_fn_in, 'r'), verbose=args.verbose)
