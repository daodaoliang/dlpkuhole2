#!/usr/bin/python3

import codecs
import json
import logging
import os
import random
import re
import requests
import sys
import time
import user_agent
from datetime import datetime

cdname = os.path.dirname(__file__)
input_folder = os.path.join(cdname, 'in')
output_folder = os.path.join(cdname, 'archive')


def parse_metadata(line):
    t = line.split()
    return {
        'pid':
        int(t[0]),
        'timestamp':
        datetime.strptime('{} {}'.format(t[1], t[2]),
                          '%Y-%m-%d %H:%M:%S').timestamp(),
        'likenum':
        int(t[3]),
        'reply':
        int(t[4]),
        'text':
        '',
        'comments': []
    }


def parse_lines(line_list):
    post_list = []
    now_post = parse_metadata(line_list[0])
    for line in line_list[1:]:
        if re.compile(
                '[0-9]+ [0-9]+-[0-9]+-[0-9]+ [0-9]+:[0-9]+:[0-9]+ -?[0-9]+ -?[0-9]+'
        ).fullmatch(line):
            if len(post_list) > 2 and now_post['pid'] == post_list[-2]['pid']:
                # 检测顺序错误的树洞
                logging.info('Rec {}'.format(now_post['pid']))
                post_list[-2] = now_post
            elif len(post_list) > 0 and now_post['pid'] == post_list[-1]['pid']:
                # 检测重复的树洞
                logging.info('Dup {}'.format(now_post['pid']))
            elif len(post_list
                     ) > 0 and now_post['pid'] != post_list[-1]['pid'] - 1:
                # 检测缺少的树洞
                # 目前没有检测第一条树洞与上个文件的最后一条之间是否有缺少
                logging.info(
                    'Mis {} {}'.format(now_post['pid'], post_list[-1]['pid']))
                for pid in range(post_list[-1]['pid'] - 1, now_post['pid'],
                                 -1):
                    post_list.append({
                        'pid': pid,
                        'timestamp': now_post['timestamp'],
                        'likenum': 0,
                        'reply': -1,
                        'text': '#MISSED\n\n',
                        'comments': []
                    })
                post_list.append(now_post)
            else:
                post_list.append(now_post)
            now_post = parse_metadata(line)
        else:
            now_post['text'] += line + '\n'
    if len(post_list) > 2 and now_post['pid'] == post_list[-2]['pid']:
        # 检测顺序错误的树洞
        logging.info('Rec {}'.format(now_post['pid']))
        post_list[-2] = now_post
    elif len(post_list) > 0 and now_post['pid'] == post_list[-1]['pid']:
        # 检测重复的树洞
        logging.info('Dup {}'.format(now_post['pid']))
    elif len(post_list) > 0 and now_post['pid'] != post_list[-1]['pid'] - 1:
        # 检测缺少的树洞
        # 目前没有检测第一条树洞与上个文件的最后一条之间是否有缺少
        logging.info('Mis {} {}'.format(now_post['pid'], post_list[-1]['pid']))
        for pid in range(post_list[-1]['pid'] - 1, now_post['pid'], -1):
            post_list.append({
                'pid': pid,
                'timestamp': now_post['timestamp'],
                'likenum': 0,
                'reply': -1,
                'text': '#MISSED\n\n',
                'comments': []
            })
        post_list.append(now_post)
    else:
        post_list.append(now_post)
    return post_list


def get_comment(post):
    if post['reply'] == 0:
        return post

    request_success = False
    # 尝试连接10次
    for retry_count in range(10):
        try:
            r = requests.get(
                'http://www.pkuhelper.com/services/pkuhole/api.php?action=getcomment&pid={}'.
                format(post['pid']),
                headers={'User-Agent': user_agent.generate_user_agent()},
                timeout=5)
        except Exception as e:
            pass
        else:
            request_success = True
            break
        time.sleep(2 + random.random())
        logging.info('Post {} retry {}'.format(post['pid'], retry_count))
    if not request_success:
        logging.info('Post {} request failed'.format(post['pid']))
        return post

    time.sleep(0.5 + random.random() * 0.5)
    r.encoding = 'utf-8'
    try:
        data = json.loads(r.text)
        r.close()
    except Exception as e:
        logging.info('Post {} parse json error:'.format(post['pid']))
        logging.info(str(e))
        return post

    if data['code'] != 0:
        logging.info('Post {} get comment error:'.format(post['pid']))
        logging.info(str(data))
        return post

    for comment in data['data']:
        post['comments'].append({
            'cid': int(comment['cid']),
            'timestamp': int(comment['timestamp']),
            'text': comment['text']
        })
    post['reply'] = len(post['comments'])
    return post


def parse_file(filename):
    f = codecs.open(filename, 'r', 'utf-8')
    line_list = f.read().splitlines()
    f.close()
    return map(get_comment, parse_lines(line_list))


def write_posts(filename, posts):
    g = codecs.open(filename, 'w', 'utf-8')
    for post in posts:
        g.write('#p {} {} {} {}\n{}'.format(
            post['pid'],
            datetime.fromtimestamp(int(post['timestamp'])).strftime(
                '%Y-%m-%d %H:%M:%S'), post['likenum'], post['reply'], post[
                    'text']))
        for comment in post['comments']:
            g.write('#c {} {}\n{}\n\n'.format(
                comment['cid'],
                datetime.fromtimestamp(int(comment['timestamp'])).strftime(
                    '%Y-%m-%d %H:%M:%S'), comment['text']))
    g.close()


if __name__ == '__main__':
    logging.getLogger().handlers = []
    logging.basicConfig(
        stream=sys.stdout,
        level=logging.INFO,
        format='%(asctime)s %(message)s')
    logging.getLogger('requests').setLevel(logging.WARNING)

    for root, dirs, files in os.walk(input_folder):
        for file in sorted(files):
            logging.info(file)
            write_posts(
                os.path.join(output_folder, file),
                parse_file(os.path.join(input_folder, file)))
