#! /usr/bin/env python3
if True: # imports    
    import os
    import paramiko
    from paramiko import SSHClient
    import datetime
    from datetime import date
    import time
    import json
    import pypsrp
    from pypsrp.client import Client
if True: # set json variables
    with open('cert-renew_f5.json') as f:
        js = json.load(f)
        device_ip           = js['DEVICE_IP']
        device_username     = js['DEVICE_UN']
        device_password     = js['DEVICE_PWD']
        ca_un               = js['CA_UN']
        ca_pwd              = js['CA_PWD']
        cert_country        = js['CERT_COUNTRY']
        cert_state          = js['CERT_STATE']
        cert_city           = js['CERT_CITY']
        cert_org            = js['CERT_ORG']
        cert_ou             = js['CERT_OU']
if True: # set local variables
    now = datetime.datetime.now()
    month = '{:02d}'.format(now.month)
    day = '{:02d}'.format(now.day)
    date_format = f'{now.year}{month}{day}'
    todays_date = now
    ca_ip = '''+MS CA IP HERE+'''
    ca_domain = '''+MS CA DOMAIN HERE+'''
    cert_drive = r'''+CA DRIVE CERTIFICATE DIRECTORY HERE+'''
if True: # open first ssh session to device
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(look_for_keys=False, allow_agent=False, hostname=device_ip, port=22, username=device_username, password=device_password)
if True: # get cn, cn-shortname 
    print("Getting CN and CN shortname from device...")
    stdin, stdout, stderr = ssh.exec_command('openssl x509 -noout -subject -in /config/httpd/conf/ssl.crt/server.crt')
    output = (stdout.read()).decode("utf-8")
    output_lines = output.split()
    cn_unformatted = []

    for val in output_lines:
        if 'CN' in val:
            cn_unformatted.append(val)
    
    cn_unformatted = str(cn_unformatted).strip('[]')
    cn_split = [cn_unformatted[i:i+3] for i in range(0, len(cn_unformatted), 3)]
    
    for idx, val in enumerate(cn_split):
        if 'CN' in val:
            cn_list = cn_split[idx:]
    
    cn = ''.join(cn_list).replace("/", "").replace("'", "").replace("CN=", "")
    cn_short = cn.split('.')
    cn_short = str(cn_short[0])
if True: # define csrname and certname variables
    csrname = f'{cn_short}.csr'
    certname = f'{cn_short}.cer'
if True: # generate csr
    print("Generating new CSR on device...")
    ssh.exec_command(f'openssl req -new -key /config/httpd/conf/ssl.key/server.key -out /config/httpd/conf/ssl.csr/{csrname} -subject -subj "/C={cert_country}/ST={cert_state}/L={cert_city}/O={cert_org}/OU={cert_ou}/CN={cn}"\n')
if True: # read csr to variable
    stdin, stdout, stderr = ssh.exec_command(f'cat /config/httpd/conf/ssl.csr/{csrname}')
    output = (stdout.read()).decode("utf-8")
    output_lines = output.splitlines()
    
    for idx, val in enumerate(output_lines):
        if 'BEGIN' in val:
            csr_start_index = idx

    csr_split = output_lines[csr_start_index:]
if True: # close first ssh session to device
    stdin.close()
    stdout.close()
    stdin.close()
    ssh.close()
if True: # write csr variable to local csr file
    print("Writing CSR to local file...")
    with open(f'{csrname}', 'w+') as csr:
        for l in csr_split:
            csr.write(l)
if True: # set pypsrp client connection settings to CA
    ca_client = Client(ca_ip, username=f"{ca_domain}\\{ca_un}",
                password=ca_pwd,
                cert_validation=False,
                ssl=False
                )
if True: # copy local csr file to CA with pypsrp client
    print("Copying local CSR file to CA...")
    ca_client.copy(csrname, f"{cert_drive}\\{csrname}")
if True: # 'submit'/sign csr on CA with pypsrp client
    print("Signing CSR on CA...")      
    ca_client.execute_cmd(f'certreq.exe -submit -config - {cert_drive}\\{csrname} {cert_drive}\\{certname}')
if True: # fetch cert file from CA and store as new name locally
    print("Fetching new signed certificate from CA...")
    new_certname = f'{cn_short}_{date_format}.crt'
    ca_client.fetch(f"{cert_drive}\\{certname}", new_certname)
if True: # read cert file to variable
    #new_certname = f'{cn_short}_{date_format}.crt'
    with open(new_certname, 'r+') as cert_import:
        cert_lines = cert_import.readlines()
if True: # open second ssh session to device
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(look_for_keys=False, allow_agent=False, hostname=device_ip, port=22, username=device_username, password=device_password)
if True: # import new certificate to device  
    print("Importing new certificate to device...")  
    for line in cert_lines:
        line = str(line).rstrip()
        ssh.exec_command(f'echo "{line}" >> /config/httpd/conf/ssl.crt/{new_certname}')
        time.sleep(.5)
if True: # apply new certificate as host certificate
    print("Moving to tmos and applying certificate...")
    remote_conn = ssh.invoke_shell()
    remote_conn.send('tmsh\n')
    time.sleep(3)
    remote_conn.send(f'modify /sys httpd ssl-certfile /config/httpd/conf/ssl.crt/{new_certname}\n')
    time.sleep(3)
    print("Saving sys config (this may take up to 30 seconds)...")
    remote_conn.send('save /sys config partitions all\n')
    time.sleep(20)
    print("Restarting httpd service...")
    remote_conn.send('restart /sys service httpd\n')
    time.sleep(5)
if True: # close second ssh session to device
    print("Closing connections to device...")
    remote_conn.close()
    ssh.close()
    print("Job done!")
    print("Remember to revoke the OLD certificate on the CA.")