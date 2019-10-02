#! /usr/bin/env python3
if True: # imports    
    import os
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
    with open('f5_ldap-add.json') as f:
        js = json.load(f)
        device_ip           = js['DEVICE_IP']
        device_name         = js['DEVICE_NAME']
        device_username     = js['DEVICE_UN']
        device_password     = js['DEVICE_PWD']
        cloud_onprem        = js['CLOUD']
        cloud_acct          = js['CLD_ACCOUNT']
        device_mgmt_ip      = js['MGMT_IP']
        ad_server_ip        = js['AD_IP']
        ad_server_subnet    = js['AD_SUBNET']
        ad_svcacct          = js['AD_SVCACCT']
        ad_svcacct_pwd      = js['AD_SVCACCT_PWD']
        bind_acct_ous       = js['BA_OUS']
        bind_acct_dcs       = js['BA_DCS']
        user_ous            = js['USER_OUS']
        user_dcs            = js['USER_DCS']
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
            print("Please confirm device name and cloud account (production, mgmt, etc.) and re-run script...")
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

        remote_conn.send('\n' * 5)
        for key in commands:
            print(key)
            promptfull = []
            while True:
                if not remote_conn.recv_ready():
                    remote_conn.send('\n' * 5)
                    time.sleep(float(commands[key])) 
                else:
                    remote_conn.send(str(key))
                    prompt = remote_conn.recv(4096)
                    prompt_str = prompt.decode("utf-8")
                    promptfull.append(prompt_str)
                    time.sleep(float(commands[key]))
                    break 
            output.append(promptfull)
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
        
        for c in commands:
            if interactive == True:
                stdin, stdout, stderr = client.exec_command(c)
                output = (stdout.read()).decode("utf-8")
                output_lines = output.splitlines()
                time.sleep(float(commands[c]))
                return output_lines
            else:
                stdin, stdout, stderr = client.exec_command(c)
                time.sleep(float(commands[c]))
        
        stderr.close()
        stdout.close()
        stdin.close()
        client.close()
if True: # get shell 
    print("Getting shell access (bash, tmsh, etc.)...")
    shell = get_shell_type()
if True: # get device management IP
    if device_mgmt_ip == 'NA':
        if shell == 'bash':
            command_dict = {f'tmsh show running-config sys management-ip': .5}
        else:
            command_dict = {f'show running-config sys management-ip': .5}
        call = exec_command_sock(command_dict, True)
        
        for val in call:
            if '/' in val:
                val_split = val.split()
                for nv in val_split:
                    if '/' in nv:
                        nv_split = nv.split('/')
                        for nnv in nv_split:
                            if '.' in nnv:
                                device_mgmt_ip = str(nnv)
if True: # apply management-ip firewall rules
    if cloud_onprem != "Azure":
        print("Adding BIP firewall rules for LDAP...")
        if shell == 'bash':
            command_dict = {f'tmsh modify security firewall management-ip-rules rules add {{ mvpc {{ action accept destination {{ addresses add {{ {device_mgmt_ip} }} }} source {{ addresses add {{ {ad_server_subnet} }} }} place-before last }} }}': .5}
        else:
            command_dict = {f'modify security firewall management-ip-rules rules add {{ mvpc {{ action accept destination {{ addresses add {{ {device_mgmt_ip} }} }} source {{ addresses add {{ {ad_server_subnet} }} }} place-before last }} }}': .5}
        exec_command_sock(command_dict, False)
    else:
        print("Azure not configured yet. Exiting script...")
        sys.exit()
if True: # apply LDAP configuration
    print("Adding LDAP configuration...")
    if cloud_onprem != 'Azure':
        if shell == 'bash':
            command_dict = {
                f'tmsh create auth ldap system-auth servers add {{ {ad_server_ip} }}': 1.5,
                f'tmsh modify auth ldap system-auth login-attribute samaccountname search-base-dn {user_ous},{user_dcs} bind-dn "cn={ad_svcacct},{bind_acct_ous},{bind_acct_dcs}" bind-pw {ad_svcacct_pwd}': 3,
                'tmsh modify auth remote-user default-role admin remote-console-access tmsh': 1.5,
                'tmsh modify auth source type active-directory fallback true': 1.5,
                'save sys config': 1
            }
        else:
            command_dict = {
                f'create auth ldap system-auth servers add {{ {ad_server_ip} }}': 1,
                f'modify auth ldap system-auth login-attribute samaccountname search-base-dn {user_ous},{user_dcs} bind-dn "cn={ad_svcacct},{bind_acct_ous},{bind_acct_dcs}" bind-pw {ad_svcacct_pwd}': 1,
                'modify auth remote-user default-role admin remote-console-access tmsh': 1,
                'modify auth source type active-directory fallback true': 1,
                'save sys config': 1
            }
        exec_command_sock(command_dict, False)
    else:
        print("Azure not configured yet. Exiting script...")
        sys.exit()      
if True: # validate LDAP configuration
    print("Validating LDAP...")
    # only works if the local accounts used above are NOT in AD as well
    time.sleep(13)
    try:
        get_shell_type()
    except:
        print("LDAP applied. Exiting script...")
        sys.exit()
    
    print("LDAP not applied. Please validate manually.")
    sys.exit()