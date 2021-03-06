#!/usr/bin/env python3

from timfuz import Benchmark, A_di2ds, sw_ei_vals2s, sw_eo_vals2s, sw_i_vals2s
from timing_txt2json import gen_timing4a, load_speed_json

import glob
import math
import json
import sys
from collections import OrderedDict


def gen_diffs(speed_json_f, fns_in):
    print('Loading data')
    _speedj, speed_i2s = load_speed_json(speed_json_f)

    for fn_in in fns_in:
        for val in gen_timing4a(fn_in, speed_i2s):
            # diff to get site only delay
            tsites = {}
            for k in val['t'][0].keys():
                v = val['t'][0][k] - val['t'][1][k]
                assert v >= 0
                tsites[k] = v
            yield val, tsites


# XXX: move to json converter?
def sd_parts(sd):
    '''Return site_type, site_pin, bel_type, bel_pin as non-prefixed strings'''
    # IOB_X0Y106 IOB_X0Y106/INBUF_EN IOB_X0Y106/INBUF_EN/OUT
    # print(sd['site'], sd['bel'], sd['bel_pin'])
    site_type = sd['site_type']
    site, bel_type, bel_pin = sd['bel_pin'].split('/')
    assert sd['site'] == site
    assert sd['bel'] == site + '/' + bel_type

    site_pin_str = sd['site_pin']
    if site_pin_str:
        site, site_pin = sd['site_pin'].split('/')
        assert sd['site_pin'] == sd['site'] + '/' + site_pin
    else:
        site_pin = None
    return site_type, site_pin, bel_type, bel_pin


def run(speed_json_f, fout, fns_in, verbose=0, corner=None):
    '''
    instead of writing to a simplified csv, lets just go directly to a delay format identical to what fabric uses
    Path types:
    -inter site: think these are removed for now?
        1 model
        NOTE: be careful of a net that goes external and comes back in, which isn't inter site
        definition is that it doesn't have any site pins
    -intra site
        2 models
    '''

    fout.write(
        'ico,fast_max fast_min slow_max slow_min,src_site_type,src_site,src_bel,src_bel_pin,dst_site_type,dst_site,dst_bel,dst_bel_pin\n'
    )
    for val, tsites in gen_diffs(speed_json_f, fns_in):

        def mkb(t):
            return (t['fast_max'], t['fast_min'], t['slow_max'], t['slow_min'])

        bstr = ' '.join([str(x) for x in mkb(tsites)])

        # Identify inter site transaction (SITEI)
        if not val['src']['site_pin'] and not val['dst']['site_pin']:
            # add one delay model for the path
            # XXX: can these be solved exactly?
            # might still have fanout and such

            src_site_type, _src_site_pin, src_bel_type, src_bel_pin = sd_parts(
                val['src'])
            dst_site_type, _dst_site_pin, dst_bel_type, dst_bel_pin = sd_parts(
                val['dst'])
            assert src_site_type == dst_site_type
            assert (src_bel_type, src_bel_pin) != (dst_bel_type, dst_bel_pin)

            k = sw_i_vals2s(
                src_site_type, src_bel_type, src_bel_pin, dst_bel_type,
                dst_bel_pin)
            row_ds = {k: 1}
        elif val['src']['site_pin'] and val['dst']['site_pin']:
            # if it exits a site it should enter another (possibly the same site)
            # site in (SITEI) or site out (SITEO)?
            # nah, keep things simple and just call them SITEW
            row_ds = {}

            def add_dst_delay():
                sd = val['dst']
                site_type, src_site_pin, dst_bel, dst_bel_pin = sd_parts(sd)
                k = sw_ei_vals2s(site_type, src_site_pin, dst_bel, dst_bel_pin)
                assert k not in row_ds
                row_ds[k] = 1

            def add_src_delay():
                sd = val['src']
                site_type, dst_site_pin, src_bel, src_bel_pin = sd_parts(sd)
                k = sw_eo_vals2s(site_type, src_bel, src_bel_pin, dst_site_pin)
                assert k not in row_ds
                row_ds[k] = 1

            add_dst_delay()
            add_src_delay()
        else:
            # dropped by the tcl script
            raise Exception("FIXME: handle destination but no source")

        row_ico = 0
        items = [str(row_ico), bstr]
        for k, v in sorted(row_ds.items()):
            items.append('%u %s' % (v, k))
        fout.write(','.join(items) + '\n')
    print('done')


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description=
        'Convert obscure timing4.txt into timing4s.csv (site delay variable occurances)'
    )

    parser.add_argument('--verbose', type=int, help='')
    # made a bulk conversion easier...keep?
    parser.add_argument(
        '--auto-name', action='store_true', help='timing4.txt => timing4i.csv')
    parser.add_argument(
        '--speed-json',
        default='build_speed/speed.json',
        help='Provides speed index to name translation')
    parser.add_argument('--out', default=None, help='Output timing4i.csv file')
    parser.add_argument('fns_in', nargs='+', help='Input timing4.txt files')
    args = parser.parse_args()
    bench = Benchmark()

    fnout = args.out
    if fnout is None:
        if args.auto_name:
            assert len(args.fns_in) == 1
            fnin = args.fns_in[0]
            fnout = fnin.replace('.txt', 's.csv')
            assert fnout != fnin, 'Expect .txt in'
        else:
            # practically there are too many stray prints to make this work as expected
            assert 0, 'File name required'
            fnout = '/dev/stdout'
    print("Writing to %s" % fnout)
    fout = open(fnout, 'w')

    fns_in = args.fns_in
    if not fns_in:
        fns_in = glob.glob('specimen_*/timing4.txt')

    run(
        speed_json_f=open(args.speed_json, 'r'),
        fout=fout,
        fns_in=fns_in,
        verbose=args.verbose)


if __name__ == '__main__':
    main()
