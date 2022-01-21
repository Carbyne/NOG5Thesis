def batch_iterator(iterator, batch_size):
    """Returns lists of length batch_size.

    This can be used on any iterator, for example to batch up
    SeqRecord objects from Bio.SeqIO.parse(...), or to batch
    Alignment objects from Bio.AlignIO.parse(...), or simply
    lines from a file handle.

    This is a generator function, and it returns lists of the
    entries from the supplied iterator.  Each list will have
    batch_size entries, although the final list may be shorter.
    """
    entry = True  # Make sure we loop once
    while entry:
        batch = []
        while len(batch) < batch_size:
            try:
                entry = iterator.next()
            except StopIteration:
                entry = None
            if entry is None:
                # End of file
                break
            batch.append(entry)
        if batch:
            yield batch

record_iter=SeqIO.parse(open('/path/sorted_sequences.fa'), 'fasta')
for i, batch in enumerate (batch_iterator(record_iter, 93)):
    filename='gene_%i.fasta' % (i + 1)
    with open('/path/files/' + filename, 'w') as ouput_handle:
        count=SeqIO.write(batch, ouput_handle, 'fasta')
    print ('Wrote %i records to %s' % (count, filename))