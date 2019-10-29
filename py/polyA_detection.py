import sys


def find_polyA_substrs(seq, match_score=1, mismatch_score=-1):
	scores = [ 0 ]
	starts = [ -1 ]	# keeps one index before start
	i = 0
	for ch in seq:
		to_be_added = match_score if (ch == 'T' or ch == 't') else mismatch_score
		new_score = scores[-1] + to_be_added
		new_start = starts[-1]

		if new_score <= 0:
			new_score = 0
			new_start = i

		scores.append(new_score)
		starts.append(new_start)

		i += 1

	return scores, starts

def find_longest_polyA(seq):
	scores, starts = find_polyA_substrs(seq, 1, -1)

	max_ind = 0
	for i in range(len(scores)):
		if (scores[i] > scores[max_ind]) or (scores[i] == scores[max_ind] and starts[i] < starts[max_ind]):
			max_ind = i

	# [start, end)
	start = starts[max_ind] + 1
	end = max_ind
	score = scores[max_ind]

	return start, end, score

def process_all_reads(fq_in, report_out):
	fout = open(report_out, 'w')

	with open(fq_in) as fin:
		while True:
			rname = fin.readline().strip()
			seq   = fin.readline().strip()
			comment = fin.readline().strip()
			qual  = fin.readline().strip()
			if not qual:
				break

			start, end, score = find_longest_polyA(seq)
			rid = rname.split()[0][1:]
			fout.write('{}\t{}\t{}\t{}\n'.format(rid, start, end, score))

def usage():
	print('Usage: python {} reads_FASTQ report_TSV'.format(sys.argv[0]))

def main():
	print('This script finds the longest stretch of \'A\'s for each given read.')
	args = sys.argv[1:]

	if len(args) != 2:
		usage()
		exit(1)

	fq_in = args[0]
	report_out = args[1]

	print('Input FASTQ: {}\nOutput report: {}'.format(fq_in, report_out))

	process_all_reads(fq_in, report_out)

if __name__ == '__main__':
	main()
