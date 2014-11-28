#!/usr/bin/python
__author__ = 'thales.pereira'


import sys
import time
import psutil
import smtplib
from datetime import datetime as date
import argparse
from email.mime.text import MIMEText
from subprocess import Popen
from email.mime.multipart import MIMEMultipart


class SendMail(object):

    def __init__(self, message_type=None, instance=None, memory_usage=None, procs=None, memory_limit=None):
        self.message_type = message_type
        self.instance = instance
        self.memory_usage = memory_usage
        self.procs = procs
        self.memory_limit = memory_limit
        self.smtp = smtplib.SMTP('localhost')
        self.mail_to = ['mail']
        self.mail_from = 'simon'
        self.msg = MIMEMultipart('alternative')
        self.msg['From'] = self.mail_from
        self.msg['To'] = ','.join(self.mail_to)

    def restart_success(self):

        self.msg['Subject'] = '[ SideKick Monitor ] Restarting ' + self.instance

        html = '''\
        <html>
          <head></head>
          <body>
            <p>Hello<br><br>
               The instance <b>{instance}</b> is consuming <b><font color='red'>{used_mem}Mb</font></b>.
               Since the defined limit is {limit} i'm going to perform a restart on sidekick.
            </p>
            <p>
            Best Regards,<br>
            <i>Simon</i>
            </p>
          </body>
        </html>
        '''.format(instance=self.instance, used_mem=self.memory_usage, limit=self.memory_limit)

        part1 = MIMEText(html, 'html')
        self.msg.attach(part1)

    def restart_blocked_by_running_proc(self):

        self.msg['Subject'] = '[ SideKick Monitor ] Restart pending for ' + self.instance

        html = '''\
        <html>
          <head></head>
          <body>
            <p>Hello<br><br>
               The instance <b>{instance}</b> is consuming <b><font color='red'>{used_mem}Mb</font></b>.
               But i cant perform a restart because it still have <b>{procs}</b> procs running.<br><br>
            </p>
            <p>
            Best Regards,<br>
            <i>Simon</i>
            </p>
          </body>
        </html>
        '''.format(instance=self.instance, used_mem=self.memory_usage, procs=self.procs)

        part1 = MIMEText(html, 'html')
        self.msg.attach(part1)


    def service_sidekiq_restart_failed(self):

        self.msg['Subject'] = '[ SideKick Monitor ] Failed to restart  ' + self.instance

        html = '''\
        <html>
          <head></head>
          <body>
            <p>Hello<br><br>
               It seems the command <i>service sidekiq restart </i> failed.
               Please check the logs until i have the proper logic to show the server message on this email.

            </p>
            <p>
            Best Regards,<br>
            <i>Simon</i>
            </p>
          </body>
        </html>
        '''.format(instance=self.instance, used_mem=self.memory_usage, procs=self.procs)

        part1 = MIMEText(html, 'html')
        self.msg.attach(part1)

    def sendmail(self):

        if self.message_type == 'restart_ok':
            self.restart_success()

        elif self.message_type == 'restart_blocked':
            self.restart_blocked_by_running_proc()

        elif self.message_type == 'restart_failed':
            self.service_sidekiq_restart_failed()

        self.smtp.sendmail(self.mail_from, self.mail_to, self.msg.as_string())
        self.smtp.quit()


class SuperSimon(object):

    def __init__(self, instance, wok=None, cok=None):
        self.mem = None
        self.pinfo_svc = None
        self.instance = instance
        self.sidekiq = 'sidekiq'

        try:
            self.limit_warning = int(wok)
        except:
            pass
        try:
            self.limit_critical = int(cok)
        except:
            pass

    def monitor(self):

        instance_list = []

        for proc in psutil.process_iter():
            #Filter running processes
            try:
                pinfo = proc.as_dict(attrs=['pid', 'name', 'cmdline'])
            except psutil.NoSuchProcess:
                pass
            else:
                #Excluce None processes
                try:
                    pinfo_svc = pinfo['cmdline'][0]
                except:
                    pass
                else:
                    #Finally we have the sidekiq filtered process
                    try:

                        pinfo_svc = pinfo_svc.split()

                        if pinfo_svc[0] == self.sidekiq:
                            instance_dict = dict()
                            process = psutil.Process(pinfo['pid'])
                            self.mem = int(process.memory_info_ex()[0]) / int(2 ** 20)
                            self.instance = pinfo_svc[2]
                            running_procs = int(pinfo_svc[3][1:])

                            if self.mem >= self.limit_critical:
                                instance_dict['instance'] = self.instance
                                instance_dict['mem_usage'] = self.mem
                                instance_dict['running_procs'] = running_procs
                                instance_list.append(instance_dict)
                            print '{t} instance: {i}\tmemory: {m}\trunning procs: {r}'.format(t=date.now(), i=self.instance, m=self.mem, r=running_procs)
                    except:
                        pass
                    finally:
                        self.pinfo_svc = pinfo_svc

        for i in instance_list:

            if i['running_procs'] != 0:
                send = SendMail('restart_blocked', i['instance'], i['mem_usage'], i['running_procs'])
                send.sendmail()
                break

            else:
                try:
                    print '{t} Restarting sidekick'.format(t=date.now())
                    Popen('service sidekiq restart', shell=True)
                except:
                    print '{t} Restart failed'.format(t=date.now())
                    send = SendMail('restart_failed', i['instance'], i['mem_usage'], i['running_procs'])
                    send.sendmail()
                else:
                    print '{t} Restart completed.'.format(t=date.now())
                    send = SendMail('restart_ok', i['instance'], i['mem_usage'], i['running_procs'], self.limit_critical)
                    send.sendmail()
                finally:
                    break

    def mem_checker(self):

        for proc in psutil.process_iter():
            #Filter running processes
            try:
                pinfo = proc.as_dict(attrs=['pid', 'name', 'cmdline'])

            except psutil.NoSuchProcess:
                pass

            else:
                #Excluce None processes
                try:
                    pinfo_svc = pinfo['cmdline'][0]

                except:
                    pass

                else:
                    #Finally we have the sidekiq filtered process
                    try:
                        pinfo_svc = pinfo_svc.split()
                        if pinfo_svc[2] == self.instance:

                            process = psutil.Process(pinfo['pid'])
                            self.mem = int(process.memory_info_ex()[0]) / int(2 ** 20)
                            status = {'OK': 0, 'WARNING': 1, 'CRITICAL': 2, 'UNKNOWN': 3}

                            if self.mem >= self.limit_critical:
                                print 'CRITICAL - {m}M used by {c}'.format(m=self.mem, c=self.instance)
                                sys.exit(status['CRITICAL'])

                            elif self.mem >= self.limit_warning:
                                print 'WARNING - {m}M used by {c}'.format(m=self.mem, c=self.instance)
                                sys.exit(status['WARNING'])

                            else:
                                print 'OK - {m}M used by {c}'.format(m=self.mem, c=self.instance)
                                sys.exit(status['OK'])

                    except:
                        pass
                    finally:
                        self.pinfo_svc = pinfo_svc


def options():

    parser = argparse.ArgumentParser(
        description='Simon, The SideKick Monitor'
    )
    parser.add_argument(
        '-c', '--check_memory_usage', help='Check total memory used by the instance.', action='store_true'
    )
    parser.add_argument(
        '-m', '--monitor', help='Monitor sidekiq behavior. ', action='store_true'
    )
    parser.add_argument(
        '-w', '--warning', help='Warning threshold.', action='store'
    )
    parser.add_argument(
        '-cr', '--critical', help='Critical threshold', action='store'
    )
    parser.add_argument(
        '-i', '--instance', help='set instance', action='store'
    )
    parser.add_argument(
        '-t', '--interval', help='set time interval ( in minutes )', action='store'
    )

    args = parser.parse_args()

    if args.check_memory_usage:
        go_simon = SuperSimon(args.instance, args.warning, args.critical)
        go_simon.mem_checker()

    if args.monitor:
        if int(args.critical) < 500:
            print "Critical limit cannot be lower than 500Mb"
            sys.exit(1)
        else:
            go_simon = SuperSimon(args.instance, args.warning, args.critical)
            while True:
                go_simon.monitor()
                time.sleep(int(args.interval) * 60)

if __name__ == '__main__':
    options()

