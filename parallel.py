import requests
import os
import time
import threading
from requests import Response
from argparse import ArgumentParser
from multiprocessing.dummy import Pool
from sys import exit
import re

total = 0  # to be updated by size
current = 0   # to be updated by update_bar
lastprint = time.perf_counter_ns()
blanklist = []
chunk_size = 1024 * 10
stopall = False

percentage_per_parts = 0
chunks_per_percentage = 0
completed_chunks_count = []  # number of chunks completed by each part


def printProgressBar(iteration, total, prefix='', suffix='', decimals=1, length=80, fill='█'):
    """
    Call in a loop to create terminal progress bar
    @params:
        iteration   - Required  : current iteration (Int)
        total       - Required  : total iterations (Int)
        prefix      - Optional  : prefix string (Str)
        suffix      - Optional  : suffix string (Str)
        decimals    - Optional  : positive number of decimals in percent complete (Int)
        length      - Optional  : character length of bar (Int)
        fill        - Optional  : bar fill character (Str)
    """
    percent = ("{0:." + str(decimals) + "f}").format(100 *
                                                     (iteration / float(total)))
    filledLength = int(length * iteration // total)
    bar = fill * filledLength + '-' * (length - filledLength)
    print('\r', end='')
    if len(prefix):
        print("%s " % prefix, end='')
    print('|%s| %s%% %s' % (prefix, bar, percent, suffix), end='\r')
    # Print New Line on Complete
    if iteration == total:
        print()


def print_parts_progressbar(suffix='', fill='█'):
    global current, total, completed_chunks_count, percentage_per_parts, chunks_per_percentage
    print('\r|', end='')
    i = 0
    for com in completed_chunks_count:
        # print(str(com.__class__))
        done = int(com / chunks_per_percentage)
        #xprint("Part %d : (%d/%d) Completed / Total" % (i, done, chunks_per_percentage))
        partbar = (fill * int(done)) + ('-' * int(percentage_per_parts - done))
        print(partbar, end='')
        #i += 1
    percent = ("{0:.1f}").format(100 * (current / float(total)))
    print('| %s%% %s' % (percent, suffix), end='\r')


def convert_bytes(byte):
    unit = "B"
    byte = byte * 1.0
    if(byte > 1024):
        byte = byte/1024
        unit = "KiB"
        if(byte > 1024):
            byte = byte/1024
            unit = "MiB"
            if(byte > 1024):
                byte = byte/1024
                unit = "GiB"
                if(byte > 1024):
                    byte = byte/1024
                    unit = "TiB"
                    if(byte > 1024):
                        byte = byte/1024
                        unit = "PiB"
    return "%.1f %s" % (byte, unit)


def convert_time(t):
    s = ""
    if t >= 3600:
        s = str(int(t // 3600)) + "h "
        t = t % 3600
    if t >= 60:
        s += str(int(t // 60)) + "m "
        t = t % 60
    s += str(int(t)) + "s"
    return s


def update_bar(interval):
    global current, total
    oldcurrent = current
    #print(time.perf_counter_ns(), lastprint)
    while not stopall:
        downloaded = current - oldcurrent
        rem = total - current
        oldcurrent = current
        speed = downloaded / interval
        remtime = 0
        if speed > 0:
            remtime = rem / speed
        print_parts_progressbar(suffix="(%s/%s) (%6s/s, %s)" %
                                (convert_bytes(current), convert_bytes(total), convert_bytes(speed),
                                 convert_time(remtime)))
        # printProgressBar(current, total, \
        #                suffix="(%10s/%10s)\t" % (convert_bytes(current), convert_bytes(total)))
        time.sleep(interval)


def update_value():
    global current, chunk_size
    current = current + chunk_size


def resume_download(resume_header):
    global current, completed_chunks_count
    chunk_size = resume_header[3]
    #print("[Get] Getting ", resume_header[0]['Range'])
    f = requests.get(
        link, headers=resume_header[0], stream=True,  verify=True, allow_redirects=True)
    numpart = resume_header[2]
    with open("temp_%s.part%d" % (resume_header[1], resume_header[2]), "wb") as fd:
        for chunk in f.iter_content(chunk_size):
            fd.write(chunk)
            current += chunk_size
            completed_chunks_count[numpart] += 1
            if stopall:
                break
            # printerPool.apply_async(update_value)
        fd.flush()
        fd.close()
    #print("[Info] Getting ", resume_header[0]['Range'], " done!")
    f.close()


def check_positive(value):
    ivalue = int(value)
    if ivalue <= 0:
        raise argparse.ArgumentTypeError(
            "%s is an invalid positive int value" % value)
    return ivalue


def check_positive_float(value):
    ivalue = float(value)
    if ivalue <= 0:
        raise argparse.ArgumentTypeError(
            "%s is an invalid positive float value" % value)
    return ivalue


regex = re.compile(
    r'^(?:http|ftp)s?://'  # http:// or https://
    # domain...
    r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'
    r'localhost|'  # localhost...
    r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
    r'(?::\d+)?'  # optional port
    r'(?:/?|[/?]\S+)$', re.IGNORECASE)

if __name__ == "__main__":

    argparser = ArgumentParser()
    argparser.add_argument("-l", "--link", metavar="<link_to_the_file>",
                           help="Link of the file to download", required=True)
    argparser.add_argument("-p", "--parallel", metavar="<no_of_parallel_downloads>",
                           type=check_positive, help="No of simultaneous downlads", required=True)
    argparser.add_argument("-c", "--chunk", metavar="<size_of_each_chunk_in_bytes>",
                           type=check_positive,
                           help="Size of each chunk to be downloaded (in bytes)",
                           required=False, default=1024*10)
    argparser.add_argument("-u", "--update", metavar="<update_interval_in_seconds>",
                           type=check_positive_float,
                           help="Time interval to update progress (in seconds)",
                           required=False, default=1)
    args = argparser.parse_args()

    if re.match(regex, args.link) is None:
        print("[Error] Bad url '%s'!" % args.link)
        exit(1)

    link = args.link
    parallel_download = args.parallel
    chunk_size = args.chunk
    update_interval = args.update

    print("[Get] Getting content length")
    try:
        resp = requests.get(link, stream=True)
    except:
        print("[Error] Given url does not exist or is not available at the moment!")
        exit(1)

    details = resp.headers
    print(details)
    size = int(details['Content-Length'])
    total = size
    name = link.split('/')[-1]
    print("[Info] Content Length : %s" % convert_bytes(size))
    print("[Info] Number of parallel connections : %d" % parallel_download)
    partsize = size/parallel_download
    # partsize = 1024     # download in 1MiB parts
    print("[Info] Size of each part : %s" % convert_bytes(partsize))
    print("[Info] Preparing resume headers")

    partstart = 0
    partend = partsize
    partscount = total // partsize
    parts = 0
    number_of_chunks = total // chunk_size
    if number_of_chunks == 0:
        print("[Error] Chunk size is greater than the size of the file!")
        exit(1)
    chunks_per_percentage = number_of_chunks // 100
    percentage_per_parts = 100 // partscount

    headers = []

    while parts < (partscount - 1):  # Accomodate all extra bytes in the last part separately
        headers.append(
            ({'Range': 'bytes=%d-%d' % (partstart, partend)}, name, parts, chunk_size))
        partstart = partend + 1
        partend = partstart + partsize
        parts = parts + 1
        completed_chunks_count.append(0)

    headers.append(
        ({'Range': 'bytes=%d-' % (partstart)}, name, parts, chunk_size))
    completed_chunks_count.append(0)

    print("[Info] Creating pool")
    pool = Pool(parallel_download)
    printerPool = Pool(1)

    stopnow = threading.Event()

    try:
        print("[Info] Starting download")
        printerPool.apply_async(update_bar, args=(update_interval,))
        pool.map(resume_download, headers)
        stopall = True
        printerPool.close()
        printerPool.join()
    except (InterruptedError, KeyboardInterrupt):
        stopall = True
        pool.close()
        pool.join()
        printerPool.close()
        printerPool.join()
        print("\n[Error] Process interrupted! Deleting all downloaded parts!")
        parts = 0
        while parts < len(headers):
            partname = "temp_%s.part%d" % (name, parts)
            parts = parts + 1
            try:
                os.remove(partname)
            except:
                pass
        exit(1)

    print("\n[Info] Joining downloaded parts")
    parts = 0
    save = open(name, "wb")
    while parts < len(headers):
        partname = "temp_%s.part%d" % (name, parts)
        with open(partname, "rb") as fd:
            c = fd.read()
            save.write(c)
            save.flush()
            fd.close()
        os.remove(partname)
        parts = parts + 1
    save.flush()
    save.close()
    pool.close()
    print("[Info] Download complete!")
#resume_download(link, 0, 100)
