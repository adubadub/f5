#! /usr/bin/env python3
if True: # imports    
    import os
    import sys
    import subprocess
    import csv
    import json
    import time
    from zipfile import ZipFile
    import paramiko
    from scp import SCPClient
    import pypsrp
    from pypsrp.client import Client
if True: # set json variables
    with open('f5_backup.json') as f:
        js = json.load(f)
        backup_server_un    = js['SERVER_UN']
        backup_server_pwd   = js['SERVER_PWD']
        hosts_pwd           = js['HOSTS_PWD']
if True: # set local variables
    date_format = time.strftime("%Y%m%d")
    backup_server_ip = '+IP OF BACKUP SERVER HERE+'
    backup_server_domain = '+DOMAIN OF BACKUP SERVER HERE+'
    backup_drive = '+DRIVE WHERE BACKUPS ARE STORED ON SERVER HERE+'
if True: # set pypsrp client connection settings to CA
    backup_server_client = Client(backup_server_ip, username=f"{backup_server_domain}\\{backup_server_un}",
                password=backup_server_pwd,
                cert_validation=False,
                ssl=False
                )
if True: # define device connect function
    def Connect(dev, addr, un, pwd):
        client = paramiko.SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(addr, port=22, username=un, password=pwd, look_for_keys=False, timeout=10)
        channel = client.invoke_shell()

        stdin = channel.makefile('wb')
        stdout = channel.makefile('rb')
        stdin.write(f'''
        tmsh
        modify cli preference pager disabled display-threshold 0
        save sys ucs F5_{dev}_{date_format}.ucs
        cd /Common
        show running-config all-properties
        cd /managed
        show running-config all-properties
        quit
        exit
        ''')
        output = stdout.read()

        stdin.close()
        stdout.close()
        client.close()
        return output
if True: # define get file SCP function
    def SCP(dev, addr, un, pwd):
        scp = paramiko.SSHClient()
        scp.load_system_host_keys()
        scp.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        scp.connect(addr, port=22, username=un, password=pwd, look_for_keys=False, timeout=10)
        scp = SCPClient(scp.get_transport())
        
        scp.get(f'/var/local/ucs/F5_{dev}_{date_format}.ucs', f'F5-UCS_{dev}_{date_format}.ucs')

        scp.close()
        return f'F5-UCS_{dev}_{date_format}.ucs'
if True: # find and move hosts.zip to workspace
    # encrypted zip file containing hosts.csv 
    # keep one directory up
    cp_file = subprocess.Popen('cp ../hosts.zip hosts.zip', stdout=subprocess.PIPE, shell=True)
    run = cp_file.communicate()
    extract_file = subprocess.Popen(f'7z e hosts.zip -p{hosts_pwd}', stdout=subprocess.PIPE, shell=True)
    run = extract_file.communicate()
if True: # open hosts file, get backups and copy to backup server
    # hosts.csv containing device type, hostname, ip, username and password
    with open('hosts.csv') as csvfile:
        read_csv = csv.reader(csvfile, delimiter=',')
        for row in read_csv:
            if row[0] == 'F5' and row[7] == 'Yes':
                backup_file = open(f'F5-Backup_{row[1]}_{date_format}.txt', 'w+')
                backup = Connect(row[1], row[2], row[3], row[4])
                backup = backup.decode('utf-8')
                for l in backup:
                    backup_file.write(l)
                ucs_filename = SCP(row[1], row[2], row[3], row[4])
                ucs_filename = str(ucs_filename)
                backup_server_client.copy(f"F5-Backup_{row[1]}_{date_format}.txt", f"{backup_drive}\\F5-Backup_{row[1]}_{date_format}.txt")
                backup_server_client.copy(f"{ucs_filename}", f"{backup_drive}\\UCS\\{ucs_filename}")
                backup_file.close()
                remove_file1 = subprocess.Popen(f'rm F5-Backup_{row[1]}_{date_format}.txt', stdout=subprocess.PIPE, shell=True)
                remove_file1.communicate()
                remove_file2 = subprocess.Popen(f'rm {ucs_filename}', stdout=subprocess.PIPE, shell=True)
                remove_file2.communicate()
if True: # remove temp files and exit script
    remove_csv = subprocess.Popen(f'rm hosts.csv', stdout=subprocess.PIPE, shell=True)
    remove_csv.communicate()
    remove_zip = subprocess.Popen(f'rm hosts.zip', stdout=subprocess.PIPE, shell=True)
    remove_zip.communicate()
    sys.exit()