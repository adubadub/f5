#! /usr/bin/env python3
if True: # imports    
    import os
    import sys
    import paramiko
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
if True: # define connect_ssh function
    def connect_ssh(commands, interactive):
        client = paramiko.SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(device_ip, port=22, username=device_username, password=device_password, look_for_keys=False, timeout=10)
        
        if interactive == True:
            if type(commands) == list:
                for c in commands:
                    stdin, stdout, stderr = client.exec_command(c)
                    output = (stdout.read()).decode("utf-8")
                    output_lines = output.split()
                    return output_lines
            else:
                stdin, stdout, stderr = client.exec_command(commands)
                output = (stdout.read()).decode("utf-8")
                output_lines = output.split()
                return output_lines
        else:
            stdin, stdout, stderr = client.exec_command(commands)
        
        stderr.close()
        stdout.close()
        stdin.close()
        client.close()
if True: # define remote_conn_send function
    def remote_conn_send(commands):
        client = paramiko.SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(device_ip, port=22, username=device_username, password=device_password, look_for_keys=False, timeout=10)
        remote_conn = client.invoke_shell()

        for key in commands:
            if 'save' in key:
                print("Saving sys config (this may take up to 30 seconds)...")
                remote_conn.send(key)
                time.sleep(int(command_dict[key]))
            elif 'restart' in key:
                print("Restarting httpd service...")
                remote_conn.send(key)
                time.sleep(int(command_dict[key]))
            else:
                remote_conn.send(str(key))
                time.sleep(int(command_dict[key]))
        
        remote_conn.close()
        client.close()
if True: # get cn, cn-shortname 
    print("Getting CN and CN shortname from device...")
    call = connect_ssh('openssl x509 -noout -subject -in /config/httpd/conf/ssl.crt/server.crt', True)
    cn_unformatted = []
    
    for val in call:
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
    connect_ssh(f'openssl req -new -key /config/httpd/conf/ssl.key/server.key -out /config/httpd/conf/ssl.csr/{csrname} -subject -subj "/C={cert_country}/ST={cert_state}/L={cert_city}/O={cert_org}/OU={cert_ou}/CN={cn}"', False)
if True: # read csr to variable
    call = connect_ssh(f'cat /config/httpd/conf/ssl.csr/{csrname}', True)

    for idx, val in enumerate(call):
        if 'BEGIN' in val:
            csr_start_index = idx

    csr_split = call[csr_start_index:]
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
    ## uncomment to test without CA
    #new_certname = f'{cn_short}_{date_format}.crt'
    with open(new_certname, 'r+') as cert_import:
        cert_lines = cert_import.readlines()
if True: # import new certificate to device  
    print("Importing new certificate to device...")  
    for line in cert_lines:
        line = str(line).rstrip()
        connect_ssh(f'echo "{line}" >> /config/httpd/conf/ssl.crt/{new_certname}', False)
        time.sleep(.5)
if True: # apply new certificate as host certificate
    print("Moving to tmos and applying certificate...")
    command_dict = {
        # command and time sleep parameters
        'tmsh\n': 3,
        f'modify /sys httpd ssl-certfile /config/httpd/conf/ssl.crt/{new_certname}\n': 5,
        'save /sys config partitions all\n': 20,
        'restart /sys service httpd\n': 5
    }
    
    remote_conn_send(command_dict)
if True: # close script
    print("Job done!")
    print("Remember to revoke the OLD certificate on the CA.")
    sys.exit()