#! /usr/bin/env python3
if True: # Imports
    import sys
    import subprocess
    import json
    import time
    import py_write
    import pypsrp
    from pypsrp.client import Client
if True: # Set environment variables
    with open('create-pys_scm.json') as f:
        js = json.load(f)
        backup_server_un        = js['BS_UN']
        backup_server_pwd       = js['BS_PWD']
        scm_url                 = js['SCM_URL']
        scm_un                  = js['SCM_UN']
        scm_pwd                 = js['SCM_PWD']
        scm_email               = js['SCM_EMAIL']
        repo_url                = js['REPO_URL']
        repo_name               = js['REPO_NAME']
if True: # Set local variables
    date_format             = time.strftime("%Y%m%d")
    new_branch              = f'py-updates_{date_format}'
    backup_server_ip        = '+BACKUP SERVER IP HERE+'
    backup_server_domain    = '+BACKUP SERVER DOMAIN HERE+'
    backup_drive            = '+DRIVE WHERE BACK-UPS ARE SAVED+'
    device_files            = []
    local_dev_files         = []
    device                  = []
if True: # Set pypsrp client 
    backup_server_client = Client(backup_server_ip, username=f"{backup_server_domain}\\{backup_server_un}",
                password=backup_server_pwd,
                cert_validation=False,
                ssl=False
                )
if True: # Create file directories
    command = subprocess.Popen('mkdir config_files', stdout=subprocess.PIPE, shell=True)
    run = command.communicate()
    command = subprocess.Popen('mkdir py_files', stdout=subprocess.PIPE, shell=True)
    run = command.communicate()
if True: # Get list of backup files from backup server
    file_out = backup_server_client.execute_cmd(f'dir "{backup_drive}"')
    filelist = file_out[0]
    filelist = filelist.strip()
    files = filelist.splitlines()

    for val in files:
        val_list = val.split()
        for v in val_list:
            if 'F5' in v and 'txt' in v:
                f_split = v.split('\\')
                filename = str(f_split[0])
                device_files.append(filename)
if True: # Fetch backup files from backup server
    for f in device_files:
        backup_server_client.fetch(f'{backup_drive}\\{f}', f)
        command = subprocess.Popen(f'mv {f} config_files/{f}', stdout=subprocess.PIPE, shell=True)
        run = command.communicate()
if True: # Generate applicable local device file list
    command = subprocess.Popen('ls config_files/', stdout=subprocess.PIPE, shell=True)
    run = command.communicate()

    for v in run:
        if type(v) == bytes:
            local_dev_files.append(v.decode())
    for v in local_dev_files:
        local_file_list = v.split()
    for val in local_file_list:
        if 'txt' in val:
            device.append(val)
if True: # Write py config files
    for dev in device:
        py_write.BUILD(dev)
        device_short = dev.split('.')
        device_short = device_short[0]
        dev_short_split = device_short.split('_')
        devname = dev_short_split[1]
        command = subprocess.Popen(f'mv {device_short}.py py_files/{devname}.py', stdout=subprocess.PIPE, shell=True)
        run = command.communicate()
if True: # Remove local backup files
    command = subprocess.Popen(f'rm -r config_files/', stdout=subprocess.PIPE, shell=True)
    run = command.communicate()
if True: # Copy local py files to repository directory
    command = subprocess.Popen(f'cp -r py_files/ {repo_name}/f5/py_files/', stdout=subprocess.PIPE, shell=True)
    run = command.communicate()
if True: # Create new branch with updated py files and commit/push to repo
    send_commands = [ 
        f'(cd {repo_name}/f5 && command git checkout -b {new_branch})',
        f'(cd {repo_name}/f5 && git add py_files/)', 
        f'(cd {repo_name}/f5 && git commit -m "py add {date_format}")', 
        f'(cd {repo_name}/f5 && git push https://{scm_un}:{scm_pwd}@{repo_url} --all)',
        f'(cd {repo_name}/f5 && git checkout master)'
        ]

    for c in send_commands:
        cmd = subprocess.Popen(c, stdout=subprocess.PIPE, shell=True)
        run = cmd.communicate()
        time.sleep(.5)
if True: # Create PR for new branch (below example for BitBucket API)
    cmd = f'''
    curl -X POST -H "Content-Type: application/json" -u {scm_email}:{scm_pwd} {scm_url}{scm_un}/{repo_name}/pullrequests -d '{{ "title": "merge py updates", "description": "py-updates {date_format}", "source": {{ "branch": {{ "name": "{new_branch}" }}, "repository": {{ "full_name": "{scm_un}/{repo_name}" }} }}, "destination": {{ "branch": {{ "name": "master" }} }}, "close_source_branch": false }}'
    '''
    command = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)
    run = command.communicate()
if True: # Close script
    sys.exit()