#!/usr/bin/env python3
import argparse
import matplotlib as mpl
mpl.use('Agg')
import matplotlib.pyplot as pp
import numpy as np
from scipy.ndimage import gaussian_filter1d
from scipy.signal import find_peaks

def parse_args():
    parser = argparse.ArgumentParser(
        description="Cluster aligned reads into isoforms")
    parser.add_argument("-p",
                        "--paf",
                        type=str,
                        required=True,
                        help="Path to PAF file of read alignments")
    parser.add_argument("-t",
                        "--tsv",
                        type=str,
                        required=True,
                        help="Path to TSV file")
    parser.add_argument("-s",
                        "--sigma",
                        type=float,
                        default=5.0,
                        help="Sigma value for gaussian_filter1d")
    parser.add_argument("-op",
                        "--out-prefix",
                        type=str,
                        required=True,
                        help="Output prefix that does not include .TXT part")
    args = parser.parse_args()
    return args

def read_paf(paf, range_len=5):
    is_first = True
    pos_to_rid = list()
    read_name_to_id = dict()
    rid_to_intervals = dict()
    for line in open(paf):
        line = line.rstrip().split('\t')
        if is_first:
            t_len = int(line[6])
            t_name = line[5]
            is_first = False
            pos_to_rid = [set() for _ in range(t_len)]
        if t_len != int(line[6]) or t_name != line[5]:
            print("Multiple targets detected in PAF file!", file=stderr)
            print(line, file=stderr)
            exit(-1)
        name = line[0]
        if not name in read_name_to_id:
            rid = len(read_name_to_id)
            read_name_to_id[name] = rid
            rid_to_intervals[rid] = list()
        rid = read_name_to_id[name]
        if any('oc:c:1' in tag for tag in line[12:]):
            t_start = max(0, int(line[7]) - 1)
            t_end = int(line[8]) + 1
            q_start = max(0, int(line[2]) - 1)
            q_end = int(line[3]) + 1
            t_interval = (t_start, t_end)
            q_interval = (q_start, q_end)
            rid_to_intervals[rid].append((t_interval, q_interval))
    for intervals in rid_to_intervals.values():
        intervals.sort()
    for rid,intervals in rid_to_intervals.items():
        new_intervals = list()
        for idx,(t_interval,q_interval) in enumerate(intervals):
            if idx == 0:
                new_intervals.append((t_interval,q_interval))
                continue
            (t_interval_prv,q_interval_prv) = new_intervals[-1]
            if t_interval[0] - t_interval_prv[1] < range_len and q_interval_prv[0] - q_interval_prv[1] < range_len:
                new_intervals[-1] = (
                    (t_interval_prv[0],t_interval[1]),
                    (q_interval_prv[0],q_interval[1]),
                )
            else:
                new_intervals.append((t_interval,q_interval))
        rid_to_intervals[rid] = new_intervals
    for rid,intervals in rid_to_intervals.items():
        for (t_start, t_end),(_, _) in intervals:
            for i in range(t_start, t_end):
                pos_to_rid[i].add(rid)
    return pos_to_rid,rid_to_intervals,read_name_to_id

def get_brks(tsv):
    """
    Get splicing breakpoints from annotation TSV file for plotting purposes only.
    """
    brks = set()
    for line in open(tsv):
        line = line.rstrip().split()
        for i in line[3].split(','):
            brks.add(int(i.split('-')[0]))
            brks.add(int(i.split('-')[1]))
    return sorted(brks)

def get_splice(gene_len, rid_to_intervals):
    """
    Get splicing in and out for each postion on the gene.
    """
    X = [x for x in range(0,gene_len+1)]
    Y_i = np.zeros(len(X))
    Y_o = np.zeros(len(X))
    for rid,intervals in rid_to_intervals.items():
        for (t_start, t_end),(_, _) in intervals:
            Y_i[t_start] =+1
            Y_o[t_end]   =+1
    Y_a = Y_i + Y_o
    return X, Y_i, Y_o, Y_a

def get_high_var_peaks(peaks, Y_roll):
    thresh = Y_roll.mean() + 3*Y_roll.std()
    idxs = list()
    for idx,p in enumerate(peaks):
        if Y_roll[p] > thresh:
            idxs.append(idx)
    return idxs

def get_desert_bound_peaks(peaks, pos_to_rid, width=50):
    """
    Returns peak indices of peaks that neighbor a region of deserts of size >= 50.
    """
    idxs = list()
    for idx,(a,b) in enumerate(zip(peaks[:-1], peaks[1:])):
        if b-a < width:
            continue
        s = a
        for i in range(a+1,b):
            if len(pos_to_rid[i]) > 0:
                s = i
            if i - s >= width:
                idxs.append(idx)
                break
    return idxs

def plot(Y_roll, peaks, peaks_opt_idxs, peaks_dessert, peaks_variance, brks, pos_to_rid, outpath):
    pp.figure(figsize=(20,5))
    pp.xlabel('Gene position')
    pp.ylabel('# of read splicing events')
    pp.plot([peaks[idx] for idx in peaks_opt_idxs], [Y_roll[p] for p in [peaks[idx] for idx in peaks_opt_idxs]], "o", label='peaks_opt_idxs', color='#e78ac3', zorder=1)
    pp.plot([peaks[idx] for idx in peaks_dessert], [Y_roll[p] for p in [peaks[idx] for idx in peaks_dessert]], ">", label='peaks_dessert', color='brown', zorder=1)
    pp.plot([peaks[idx] for idx in peaks_variance], [Y_roll[p] for p in [peaks[idx] for idx in peaks_variance]], "<", label='peaks_variance', color='green', zorder=1)
    peaks_other = set(range(len(peaks))) - set(peaks_opt_idxs) - peaks_dessert - peaks_variance
    pp.plot([peaks[idx] for idx in peaks_other], [Y_roll[p] for p in peaks_other], "x", label='peaks_other', color='#66c2a5', zorder=1)
    pp.plot(Y_roll, label='Gaussian filtered', color='#fc8d62', zorder=3)
    pp.vlines(brks,ymin=0, ymax=max(Y_roll)*1.05, colors='#8da0cb', linestyles='dashed', alpha=0.4, linewidth=1, label='Annotation splice points',zorder=4)
    # for s,e in intervals:
    #     print(peaks[s],peaks[e])
    #     pp.hlines(y=max(Y_roll)*0.75, xmin=peaks[s], xmax=peaks[e])
    #     pp.text(y=max(Y_roll)*0.80, x=peaks[s]+(peaks[e]-peaks[s])*.4, s='|p|={}'.format(e-s+1), rotation=45)
    pp.legend()
    pp.twinx()
    pp.ylabel('Coverage')
    pp.plot([len(p) for p in pos_to_rid], label='Read coverage', color='black', alpha=.4,zorder=2)
    pp.title('|p|={} |opt_p|={}'.format(len(peaks), len(peaks_opt_idxs)))
    pp.legend(loc='center right')
    pp.savefig(fname=outpath)

def optimize(peaks, C, start, end):
    cov_mem = dict()
    yea_mem = dict()
    nay_mem = dict()
    amb_mem = dict()

    print('Preomputing coverage mems...')
    for i in range(start, end):
        for j in range(i+1, end):
            cov_mem[(i,j)] = (C[j]-C[i])/(peaks[j]-peaks[i]+1)
            yea_mem[(i,j)] = cov_mem[(i,j)] > 0.9
            nay_mem[(i,j)] = cov_mem[(i,j)] < 0.1
            amb_mem[(i,j)] = np.logical_not(np.logical_xor(yea_mem[(i,j)],nay_mem[(i,j)]))

    out_mem = dict()
    def outside(i, j, k):
        if not (i,j,k) in out_mem:
            out_mem[(i,j,k)] = sum(np.logical_or(
                np.logical_xor(
                    yea_mem[(i,j)],
                    nay_mem[(j,k)]
                ),
                np.logical_xor(
                    nay_mem[(i,j)],
                    yea_mem[(j,k)]
                ),
            ))
        return out_mem[(i,j,k)]
    D = dict()
    B = dict()
    logger = dict()
    def dp(i,j,k):
        if not (i,j) in logger:
            # print('(i,j):',(i,j))
            logger[(i,j)]=None
        if not (i,j,k) in D:
            if j+1==k:
                D[(i,j,k)] = -amb_mem[(i,j)].sum() + outside(i,j,k)
                B[(i,j,k)] = (-1,-1,-1)
            else:
                max_b = (-1,-1,-1)
                max_d = float('-inf')
                for k_ in range(k+1, end):
                    cur_b = (j,k,k_)
                    cur_d = -amb_mem[(i,j)].sum() + outside(i,j,k) + dp(*cur_b)
                    if cur_d > max_d:
                        max_d = cur_d
                        max_b = cur_b
                D[(i,j,k)] = max_d
                B[(i,j,k)] = max_b
        # print('{} : {}'.format((i,j,k), D[(i,j,k)]))
        return D[(i,j,k)]
    max_b = (-1,-1,-1)
    max_d = float('-inf')
    print('DP...')
    for j in range(start+1, end):
        for k in range(j+1, end):
            # print('j,k', (j,k))
            cur_b = (start,j,k)
            cur_d = dp(*cur_b)
            if cur_d > max_d:
                max_d = cur_d
                max_b = cur_b
    return D,B,max_d,max_b

def get_coverage(peaks, pos_to_rid):
    rids_cnt = 0
    for rids in pos_to_rid:
        for rid in rids:
            if rid > rids_cnt:
                rids_cnt = rid
    rids_cnt += 1
    C = np.zeros((len(peaks), rids_cnt), dtype=np.uint32)
    for idx,(cur,nxt) in enumerate(zip(peaks[:-1],peaks[1:]), start=1):
        for pos in range(cur,nxt):
            for rid in pos_to_rid[pos]:
                C[idx,rid]+=1
    for i in range(1,len(C)):
        C[i] += C[i-1]
    return C

def main():
    args = parse_args()

    pos_to_rid,rid_to_intervals,read_name_to_id = read_paf(args.paf)
    # rid_set = set()
    # for rids in pos_to_rid:
    #     for rid in rids:
    #         rid_set.add(rid)
    # rid_set = sorted(rid_set)
    # print(rid_set[0],rid_set[-1], len(rid_set))
    brks = get_brks(args.tsv)
    if len(rid_to_intervals)>0:
        gene_len = int(open(args.paf).readline().split('\t')[6])
    else:
        gene_len = 1
    X, Y_i, Y_o, Y_a = get_splice(gene_len=gene_len, rid_to_intervals=rid_to_intervals)

    if not args.sigma > 0.0:
        print('Sigma is not positive float. Not doing any filtering')
        Y_roll=Y_a
    else:
        Y_roll=gaussian_filter1d(Y_a,args.sigma)
    peaks, _ = find_peaks(Y_roll)
    temp = list()
    temp.append(0)
    for p in peaks:
        if sum(Y_a[p-int(args.sigma):p+1+int(args.sigma)]) > 1:
            temp.append(p)
    temp.append(len(pos_to_rid))
    peaks = np.array(temp)
    peaks_opt_idxs = [0,len(peaks)-1]
    peaks_dessert = get_desert_bound_peaks(peaks, pos_to_rid)
    peaks_opt_idxs.extend(peaks_dessert)
    peaks_variance = get_high_var_peaks(peaks=peaks, Y_roll=Y_roll)
    peaks_opt_idxs.extend(peaks_variance)
    peaks_opt_idxs = sorted(set(peaks_opt_idxs))
    print(peaks_opt_idxs)
    coverage = get_coverage(peaks=peaks, pos_to_rid=pos_to_rid)
    for interval in zip(peaks_opt_idxs[:-1],peaks_opt_idxs[1:]):
        if interval[1]-interval[0]+1 < 4:
            print('Skipping interval {} since it has less than 3 breakpoints'.format(interval))
            continue
        print('Running interval {}'.format(interval))
        D,B,max_d,max_b=optimize(peaks=peaks, C=coverage, start=interval[0], end=interval[1])
        # print('Solution:')
        # print('{}-{}-{}'.format(*max_b),end='')
        peaks_opt_idxs.extend(max_b)
        while B[max_b] != (-1,-1,-1):
            assert(max_b[1:]==B[max_b][:-1])
            max_b = B[max_b]
            peaks_opt_idxs.append(max_b[2])
            # print('-{}'.format(max_b[2]),end='')
        # print()
        # break
    peaks_opt_idxs = sorted(set(peaks_opt_idxs))
    peaks_dessert=set(peaks_dessert)
    peaks_variance=set(peaks_variance)
    peaks_opt_idxs = [idx for idx in peaks_opt_idxs if not idx in peaks_dessert|peaks_variance]
    print(peaks_opt_idxs)
    plot(Y_roll=Y_roll, peaks=peaks, peaks_opt_idxs=peaks_opt_idxs, peaks_dessert=peaks_dessert, peaks_variance=peaks_variance, brks=brks, pos_to_rid=pos_to_rid, outpath='{}.pdf'.format(args.out_prefix))
    out_file = open('{}.txt'.format(args.out_prefix), 'w+')
    for i in peaks:
        print(i, file=out_file)
    out_file.close()

if __name__ == "__main__":
    main()
