#! /usr/bin/env python3
if True: # imports    
    import sys
    import subprocess
    import paramiko
    import datetime
    from datetime import date
    from dateutil import parser
    import time
    import json
    import pypsrp
    from pypsrp.client import Client
if True: # set json variables
    with open('cert-renew_f5_complete.json') as f:
        js = json.load(f)
        device_ip           = js['DEVICE_IP']
        device_name         = js['DEVICE_NAME']
        device_domain       = js['DEVICE_DOMAIN']
        device_username     = js['DEVICE_UN']
        device_password     = js['DEVICE_PWD']
        ca_un               = js['CA_UN']
        ca_pwd              = js['CA_PWD']
        cert_country        = js['CERT_COUNTRY']
        cert_state          = js['CERT_STATE']
        cert_city           = js['CERT_CITY']
        cert_org            = js['CERT_ORG']
        cert_ou             = js['CERT_OU']
        cloud_onprem        = js['CLOUD']
        cloud_acct          = js['CLD_ACCOUNT']
if True: # set local variables
    now = datetime.datetime.now()
    month = '{:02d}'.format(now.month)
    day = '{:02d}'.format(now.day)
    date_format = f'{now.year}{month}{day}'
    todays_date = now
    ca_ip = '''+MS CA IP HERE+'''
    ca_domain = '''+MS CA DOMAIN HERE+'''
    cert_drive = r'''+CA DRIVE CERTIFICATE DIRECTORY HERE+'''
if True: # get device IP if cloud
    if cloud_onprem == "AWS":
        print("Getting cloud device IP...")
        cmd1 = f'''aws ec2 describe-tags --profile {cloud_acct} \
        --filters "Name=key,Values=Name"
        '''
        proc = subprocess.Popen(cmd1, stdout=subprocess.PIPE, shell=True)
        out, err = proc.communicate()
        output = out.decode("utf-8")
        call = output.splitlines()
        names = []
        name = []

        for idx, val in enumerate(call):
            if device_name in val:
                start_index = idx - 5
                end_index = idx + 1
                instance_verbose = call[start_index:end_index]
                for idx, val in enumerate(instance_verbose):
                    if '"instance"' in val:
                        instance_output = instance_verbose
                name_split = val.split()
                for val in name_split:
                    if device_name in val:
                        names.append(val)

        dup_names = [n for n in names if names.count(n) > 1]
        if len(dup_names) > 0:
            for i in names:
                if i not in name:
                    name.append(i)
        else:
            name = [names[0]]
        device_name = str(name[0])
        device_name = device_name.replace('"', '')

        try:
            for val in instance_output:
                if 'i-' in val:
                    resource = val.split()
                    for val in resource:
                        if 'i-' in val:
                            resource_id = val.replace(',','').replace('"','')
        except NameError:
            print("Please confirm device name and cloud account (prod, test, etc.) and re-run script...")
            sys.exit()

        cmd2 = f'''aws ec2 describe-instances --profile {cloud_acct} \
        --instance-id {resource_id}
        '''
        proc = subprocess.Popen(cmd2, stdout=subprocess.PIPE, shell=True)
        out, err = proc.communicate()
        output = out.decode("utf-8")
        call = output.splitlines()
        ips_full = []
        pub_ips_full = []
        ips = []
        pub_ips = []
        accessible_ips = []
        accessible_pub_ips = []

        for val in call:
            if 'PublicIp' in val:
                ip_split = val.split()
                for idx, val in enumerate(ip_split):
                    if 'PublicIp' in val:
                        ip_addr = ip_split[idx + 1]
                        ip_addr = ip_addr.replace('[','').replace(']','').replace(',','').replace('"', '')
                        pub_ips_full.append(ip_addr)
            elif 'IpAddress' in val:
                ip_split = val.split()
                for idx, val in enumerate(ip_split):
                    if 'IpAddress' in val:
                        ip_addr = ip_split[idx + 1]
                        ip_addr = ip_addr.replace('[','').replace(']','').replace(',','').replace('"', '')
                        ips_full.append(ip_addr)

        client = paramiko.SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        if len(pub_ips_full) > 0:
            for i in pub_ips_full:
                if i not in pub_ips:
                    pub_ips.append(i)
            pub_ips = [i for i in pub_ips if i]
            for i in pub_ips:
                try:
                    client.connect(i, port=22, username=device_username, password=device_password, look_for_keys=False, timeout=10)
                    accessible_pub_ips.append(i)
                except:
                    continue
        else:
            for i in ips_full:
                if i not in ips:
                    ips.append(i)
            ips = [i for i in ips if i]
            for i in ips:
                try:
                    client.connect(i, port=22, username=device_username, password=device_password, look_for_keys=False, timeout=10)
                    accessible_ips.append(i)
                except:
                    continue
        if len(accessible_pub_ips) > 0:
            device_ip = accessible_pub_ips[0]
        else:
            device_ip = accessible_ips[0]
    elif cloud_onprem == "Azure":
        print("Azure not configured yet. Exiting script...")
        sys.exit()
if True: # define get_shell_type function
    def get_shell_type():
        client = paramiko.SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(device_ip, port=22, username=device_username, password=device_password, look_for_keys=False, timeout=10)
        remote_conn = client.invoke_shell()
        promptfull = []

        remote_conn.send('\n' * 10)
        time.sleep(3)
        while True:
            if remote_conn.recv_ready():
                prompt = remote_conn.recv(4096)
                time.sleep(1.5)
            else:
                break
            prompt_str = prompt.decode("utf-8")
            promptfull.append(prompt_str) 

        if '~' in promptfull[-1]:
            shell = 'bash'
        else:
            shell = 'tmsh'

        remote_conn.close()
        return shell
if True: # define shell_command_sock function
    def shell_command_sock(commands, interactive):
        client = paramiko.SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(device_ip, port=22, username=device_username, password=device_password, look_for_keys=False, timeout=10)
        remote_conn = client.invoke_shell()
        output = []
        dict_list = list(commands.keys())

        if commands[dict_list[1]] == 0:
            for key in commands:
                if commands[key] != 0:
                    remote_conn.send(f'{key}\n')
                    time.sleep(int(commands[key])) 
                    while True:
                        if remote_conn.recv_ready():
                            prompt = remote_conn.recv(4096)
                            time.sleep(1.5)
                        else:
                            break
                    continue
                else:
                    remote_conn.send(f'{key}\n')
                    time.sleep(.5)
                    continue
        else:
            remote_conn.send('\n' * 5)
            for key in commands:
                remote_conn.send(str(key))
                time.sleep(int(commands[key])) 
                promptfull = []
                while True:
                    if remote_conn.recv_ready():
                        prompt = remote_conn.recv(4096)
                        time.sleep(1.5)
                    else:
                        break                
                    prompt_str = prompt.decode("utf-8")
                    promptfull.append(prompt_str)  
                output.append(promptfull[-1])
                continue
       
        remote_conn.close()
        client.close()
        if interactive == True:
            return output
if True: # define exec_command_sock function
    def exec_command_sock(commands, interactive):
        client = paramiko.SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(device_ip, port=22, username=device_username, password=device_password, look_for_keys=False, timeout=10)
        
        if interactive == True:
            stdin, stdout, stderr = client.exec_command(commands)
            output = (stdout.read()).decode("utf-8")
            output_lines = output.splitlines()
            return output_lines
        else:
            stdin, stdout, stderr = client.exec_command(commands)
        
        stderr.close()
        stdout.close()
        stdin.close()
        client.close()
if True: # get shell 
    print("Getting shell access (bash, tmsh, etc.)...")
    shell = get_shell_type()
if True: # get cn, cn-shortname
    if cloud_onprem != "Azure":
        print("Getting CN and CN shortname from device...")
        if shell == 'bash':
            call = exec_command_sock('openssl x509 -noout -subject -in /config/httpd/conf/ssl.crt/server.crt', True)
        else:
            command_dict = {
                'run util bash\n':2,
                'openssl x509 -noout -subject -in /config/httpd/conf/ssl.crt/server.crt\n':1
            }
            call = shell_command_sock(command_dict, True)

        cn_unformatted = []
        
        for idx, val in enumerate(call):
            if 'CN' in val:
                cn_format = call[idx].splitlines()
                for idx, val in enumerate(cn_format):
                    if 'CN' in val:
                        cn_raw = cn_format[idx].split('/')
                        for val in cn_raw:
                            if 'CN' in val:
                                cn_unformatted.append(val)

        cn_unformatted = str(cn_unformatted).strip('[]')
        cn_split = [cn_unformatted[i:i+3] for i in range(0, len(cn_unformatted), 3)]
        
        for idx, val in enumerate(cn_split):
            if 'CN' in val:
                cn_list = cn_split[idx:]
        
        try:
            cn = ''.join(cn_list).replace("/", "").replace("'", "").replace("CN=", "")
        except NameError:
            print("Issue getting CN. Please re-run the script...")
            sys.exit()
        
        if 'localhost' in cn:
            cn = f'{device_name}.{device_domain}'
            cn_short = device_name
        else:
            cn_short = cn.split('.')
            cn_short = str(cn_short[0])
    else:
        print("Azure not configured yet. Exiting script...")
        sys.exit()
if True: # define csrname and certname variables
    ## uncomment below to test without getting cn dynamically
    #cn_short = ''
    csrname = f'{cn_short}_{date_format}.csr'
    certname = f'{cn_short}.cer'
if True: # generate csr
    print("Generating new CSR on device...")
    if shell == 'bash':
        exec_command_sock(f'openssl req -new -key /config/httpd/conf/ssl.key/server.key -out /config/httpd/conf/ssl.csr/{csrname} -subject -subj "/C={cert_country}/ST={cert_state}/L={cert_city}/O={cert_org}/OU={cert_ou}/CN={cn}"', False)
    else:
        command_dict = {
            'run util bash\n':2,
            f'openssl req -new -key /config/httpd/conf/ssl.key/server.key -out /config/httpd/conf/ssl.csr/{csrname} -subject -subj "/C={cert_country}/ST={cert_state}/L={cert_city}/O={cert_org}/OU={cert_ou}/CN={cn}"\n':1.5
        }
        shell_command_sock(command_dict, False)
if True: # read csr to variable
    if shell == 'bash':
        call = exec_command_sock(f'cat /config/httpd/conf/ssl.csr/{csrname}', True)
        for idx, val in enumerate(call):
            if 'BEGIN' in val:
                csr_start_index = idx
        csr_split = call[csr_start_index:]
    else:
        command_dict = {
            'run util bash\n':1,
            f'cat /config/httpd/conf/ssl.csr/{csrname}\n':1.5
        }
        call = shell_command_sock(command_dict, True)
        for idx, val in enumerate(call):
            if 'BEGIN' in val:
                val_splitlines = val.splitlines()
                for idx, val in enumerate(val_splitlines):
                    if 'BEGIN' in val:
                        csr_start_index = idx
                    if 'REQUEST--' in val:
                        csr_end_index = idx
                csr_split = val_splitlines[csr_start_index:csr_end_index + 1]
if True: # write csr variable to local csr file
    print("Writing CSR to local file...")
    with open(f'{csrname}', 'w+') as csr:
        try:
            for l in csr_split:
                csr.write(l)
        except NameError:
            print("Issue generating CSR. Please re-run the script...")
            sys.exit()
if False: # set pypsrp client connection settings to CA
    ca_client = Client(ca_ip, username=f"{ca_domain}\\{ca_un}",
                password=ca_pwd,
                cert_validation=False,
                ssl=False
                )
if False: # copy local csr file to CA with pypsrp client
    print("Copying local CSR file to CA...")
    ca_client.copy(csrname, f"{cert_drive}\\{csrname}")
if False: # 'submit'/sign csr on CA with pypsrp client
    print("Signing CSR on CA...")      
    ca_client.execute_cmd(f'certreq.exe -submit -config - {cert_drive}\\{csrname} {cert_drive}\\{certname}')
if False: # fetch cert file from CA and store as new name locally
    print("Fetching new signed certificate from CA...")
    new_certname = f'{cn_short}_{date_format}.crt'
    ca_client.fetch(f"{cert_drive}\\{certname}", new_certname)
if True: # read cert file to variable
    ## uncomment below to test without CA
    #new_certname = f'{cn_short}_{date_format}.crt'
    with open(new_certname, 'r+') as cert_import:
        cert_lines = cert_import.readlines()
if True: # import new certificate to device  
    print("Importing new certificate to device...")    
    if shell == 'bash':
        command_dict = {
        }
        for line in cert_lines:
            line = str(line).rstrip()
            command_dict.update( {f'echo "{line}" >> /config/httpd/conf/ssl.crt/{new_certname}\n':0} )
        shell_command_sock(command_dict, False)
    else:
        command_dict = {
            'run util bash\n':1
        }
        for line in cert_lines:
            line = str(line).rstrip()
            command_dict.update( {f'echo "{line}" >> /config/httpd/conf/ssl.crt/{new_certname}\n':0} )
        shell_command_sock(command_dict, False)
if True: # apply new certificate as host certificate
    print("Applying certificate and saving...")
    if shell == 'bash':
        command_dict = {
            # command and time.sleep parameters
            'tmsh\n': 5,
            f'modify /sys httpd ssl-certfile /config/httpd/conf/ssl.crt/{new_certname}\n': 5,
            'save /sys config partitions all\n': 20,
            'restart /sys service httpd\n': 5
        }
    else:
        command_dict = {
            f'modify /sys httpd ssl-certfile /config/httpd/conf/ssl.crt/{new_certname}\n': 5,
            'save /sys config partitions all\n': 20,
            'restart /sys service httpd\n': 5
        }
    shell_command_sock(command_dict, False)
if True: # close script
    print("Job done!")
    print("Remember to revoke the OLD certificate on the CA.")
    sys.exit()