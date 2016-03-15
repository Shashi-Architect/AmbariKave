##############################################################################
#
# Copyright 2015 KPMG N.V. (unless otherwise stated)
#
# Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
##############################################################################
import re
import socket
import json

from resource_management import *

config = Script.get_config()

hostname = config["hostname"]

amb_server = default("/clusterHostInfo/ambari_server_host", [False])[0]

ipa_server = default("/clusterHostInfo/freeipa_server_hosts", [False])[0]

ipa_server_ip_address = socket.gethostbyname(ipa_server)
if not ipa_server_ip_address:
    raise Exception('ipa_server_ip_address couldn\'t be determined')

directory_password = default('configurations/freeipa/directory_password', False)
if not directory_password or len(directory_password) < 8:
    raise Exception('FreeIPA directory_password: \'%s\' isn\'t acceptable (min 8 char long)' % directory_password)
else:
    Logger.sensitive_strings[directory_password] = "[PROTECTED]"

ldap_bind_password = default('configurations/freeipa/ldap_bind_password', False)
if not ldap_bind_password or len(ldap_bind_password) < 8:
    raise Exception('FreeIPA ldap_bind_password: \'%s\' isn\'t acceptable (min 8 char long)' % ldap_bind_password)
else:
    Logger.sensitive_strings[ldap_bind_password] = "[PROTECTED]"

hostname_components = config["hostname"].split('.')
if len(hostname_components) < 3:
    raise Exception('FreeIPA hostname is not a FQDN. installation not possible')
domain = '.'.join(hostname_components[1:])
realm = '.'.join(hostname_components[1:]).upper()
realm_ldap = 'dc=' + ',dc='.join(hostname_components[1:])

install_with_dns = default('configurations/freeipa/install_with_dns', True)
default_shell = default('configurations/freeipa/default_shell', '/bin/bash')

# Only except IPv4 for now
forwarders = default('configurations/freeipa/forwarders', '8.8.8.8').split(',')
forwarders = [forwarder.strip() for forwarder in forwarders]
forwarders = [forwarder for forwarder in forwarders if re.match('\\d+\\.\\d+\\.\\d+\\.\\d+', forwarder)]

client_init_wait = default('configurations/freeipa/client_init_wait', 600)

all_hosts = default("/clusterHostInfo/all_hosts", [hostname])

# An explosion of all the clustHostInfo params generated by:
# ambari/ambari-server/src/main/java/org/apache/ambari/server/utils/StageUtils.java
# these are used to reversly generate the client keytabs
cluster_host_info = {
    'ambari_server_host': set(default("/clusterHostInfo/ambari_server_host", [])),
    'namenode_host': set(default("/clusterHostInfo/namenode_host", [])),
    'jtnode_host': set(default("/clusterHostInfo/jtnode_host", [])),
    'snamenode_host': set(default("/clusterHostInfo/snamenode_host", [])),
    'rm_host': set(default("/clusterHostInfo/rm_host", [])),
    'nm_hosts': set(default("/clusterHostInfo/nm_hosts", [])),
    'hs_host': set(default("/clusterHostInfo/hs_host", [])),
    'journalnode_hosts': set(default("/clusterHostInfo/journalnode_hosts", [])),
    'zkfc_hosts': set(default("/clusterHostInfo/zkfc_hosts", [])),
    'zookeeper_hosts': set(default("/clusterHostInfo/zookeeper_hosts", [])),
    'flume_hosts': set(default("/clusterHostInfo/flume_hosts", [])),
    'hbase_master_hosts': set(default("/clusterHostInfo/hbase_master_hosts", [])),
    'hbase_rs_hosts': set(default("/clusterHostInfo/hbase_rs_hosts", [])),
    'hive_server_host': set(default("/clusterHostInfo/hive_server_host", [])),
    'hive_metastore_host': set(default("/clusterHostInfo/hive_metastore_host", [])),
    'oozie_server': set(default("/clusterHostInfo/oozie_server", [])),
    'webhcat_server_host': set(default("/clusterHostInfo/webhcat_server_host", [])),
    'hive_mysql_host': set(default("/clusterHostInfo/hive_mysql_host", [])),
    'dashboard_host': set(default("/clusterHostInfo/dashboard_host", [])),
    'ganglia_server_host': set(default("/clusterHostInfo/ganglia_server_host", [])),
    'slave_hosts': set(default("/clusterHostInfo/slave_hosts", [])),
    'mapred_tt_hosts': set(default("/clusterHostInfo/mapred_tt_hosts", [])),
    'kdc_host': set(default("/clusterHostInfo/kdc_host", [])),
    'kerberos_adminclient_host': set(default("/clusterHostInfo/kerberos_adminclient_host", [])),
    'nagios_server': default('/clusterHostInfo/nagios_server_host', []),
    'storm_drpc_server': set(default('/clusterHostInfo/stormsd_drpc_server_hosts', [])
                             + default('/clusterHostInfo/drpc_server_hosts', [])),
    'storm_ui_server': set(default('/clusterHostInfo/stormsd_ui_server_hosts', [])
                           + default('/clusterHostInfo/storm_ui_server_hosts', [])),
    'app_timeline_server': set(default('/clusterHostInfo/app_timeline_server_hosts', [])),
    'falcon_server': set(default('/clusterHostInfo/falcon_server_hosts', [])),
    'knox_server': set(default('/clusterHostInfo/knox_gateway_hosts', [])),
    'accumulo_gc_hosts': set(default('/clusterHostInfo/accumulo_gc_hosts', [])),
    'kafka_hosts': set(default('/clusterHostInfo/kafka_broker_hosts', [])),
    'atlas_hosts': set(default('/clusterHostInfo/atlas_server_hosts', [])),
    'ams_hosts': set(default('/clusterHostInfo/ams_hosts', []))

}

# real users that must be created as principals in FreeIPA, with a keytab
headless_users = default('configurations/freeipa/headless_users', """{
    "Ambari Smoke Test User": {"identity": "ambari-qa", "file": "/etc/security/keytabs/smokeuser.headless.keytab",
                               "user": "hdfs", "group": "hadoop", "permissions": "440"},
    "HDFS User": {"identity": "hdfs", "file": "/etc/security/keytabs/hdfs.headless.keytab",
                  "user": "hdfs", "group": "hadoop", "permissions": "440"},
    "HDFS User for nodemanager": {"identity": "hdfs", "file": "/etc/security/keytabs/hdfs.headless.keytab",
                                  "user": "hdfs", "group": "hadoop", "permissions": "440"},
    "HBase User": {"identity": "hbase", "file": "/etc/security/keytabs/hbase.headless.keytab",
                   "user": "hbase", "group": "hadoop", "permissions": "440"},
    "Storm User": {"identity": "storm", "file": "/etc/security/keytabs/storm.headless.keytab",
                   "user": "storm", "group": "hadoop", "permissions": "440"},
    "Accumulo User": {"identity": "accumulo", "file": "/etc/security/keytabs/accumulo.headless.keytab",
                   "user": "accumulo", "group": "hadoop", "permissions": "440"},
    "Accumulo Tracer User": {"identity": "tracer", "file": "/etc/security/keytabs/accumulo-tracer.headless.keytab",
                   "user": "accumulo", "group": "hadoop", "permissions": "440"},
    "Spark User": {"identity": "spark", "file": "/etc/security/keytabs/spark.headless.keytab",
                   "user": "spark", "group": "hadoop", "permissions": "440"}

}""")
headless_users = json.loads(headless_users)

service_users = default('configurations/freeipa/service_users', """{
    "HDFS SPNEGO User": {"hosts": {{namenode_host}},
                         "identity": "HTTP", "file": "/etc/security/keytabs/spnego.service.keytab",
                         "user": "root", "group": "hadoop", "permissions": "440"},
    "HDFS SPNEGO User": {"hosts": {{snamenode_host}},
                         "identity": "HTTP", "file": "/etc/security/keytabs/spnego.service.keytab",
                         "user": "root", "group": "hadoop", "permissions": "440"},
    "WebHCat SPNEGO User": {"hosts": {{webhcat_server_host}},
                            "identity": "HTTP", "file": "/etc/security/keytabs/spnego.service.keytab",
                            "user": "root", "group": "hadoop", "permissions": "440"},
    "Hive SPNEGO User": {"hosts": {{hive_server_host}},
                         "identity": "HTTP", "file": "/etc/security/keytabs/spnego.service.keytab",
                         "user": "root", "group": "hadoop", "permissions": "440"},
    "Oozie SPNEGO User": {"hosts": {{oozie_server}},
                          "identity": "HTTP", "file": "/etc/security/keytabs/spnego.service.keytab",
                          "user": "root", "group": "hadoop", "permissions": "440"},
    "History server SPNEGO User": {"hosts": {{hs_host}},
                                   "identity": "HTTP", "file": "/etc/security/keytabs/spnego.service.keytab",
                                   "user": "root", "group": "hadoop", "permissions": "440"},
    "ResourceManager SPNEGO User": {"hosts": {{rm_host}},
                                    "identity": "HTTP", "file": "/etc/security/keytabs/spnego.service.keytab",
                                    "user": "root", "group": "hadoop", "permissions": "440"},
    "NodeManager SPNEGO User": {"hosts": {{nm_hosts}},
                                "identity": "HTTP", "file": "/etc/security/keytabs/spnego.service.keytab",
                                "user": "root", "group": "hadoop", "permissions": "440"},
    "YARN ATS HTTP User": {"hosts": {{jtnode_host}},
                           "identity": "HTTP", "file": "/etc/security/keytabs/spnego.service.keytab",
                           "user": "root", "group": "hadoop", "permissions": "440"},
    "DataNode": {"hosts": {{slave_hosts}},
                 "identity": "dn", "file": "/etc/security/keytabs/dn.service.keytab",
                 "user": "hdfs", "group": "hadoop", "permissions": "400"},
    "HBase Master": {"hosts": {{hbase_master_hosts}},
                     "identity": "hbase", "file": "/etc/security/keytabs/hbase.service.keytab",
                     "user": "hbase", "group": "hadoop", "permissions": "400"},
    "HBase Master": {"hosts": {{hbase_rs_hosts}},
                     "identity": "hbase", "file": "/etc/security/keytabs/hbase.service.keytab",
                     "user": "hbase", "group": "hadoop", "permissions": "400"},
    "History Server": {"hosts": {{hs_host}},
                       "identity": "jhs", "file": "/etc/security/keytabs/jhs.service.keytab",
                       "user": "mapred", "group": "hadoop", "permissions": "400"},
    "HiveServer2": {"hosts": {{hive_server_host}},
                    "identity": "hive", "file": "/etc/security/keytabs/hive.service.keytab",
                    "user": "hive", "group": "hadoop", "permissions": "400"},
    "Hive Metastore": {"hosts": {{hive_metastore_host}},
                       "identity": "hive", "file": "/etc/security/keytabs/hive.service.keytab",
                       "user": "hive", "group": "hadoop", "permissions": "400"},
    "NameNode": {"hosts": {{namenode_host}},
                 "identity": "nn", "file": "/etc/security/keytabs/nn.service.keytab",
                 "user": "hdfs", "group": "hadoop", "permissions": "400"},
    "Secondary NameNode": {"hosts": {{snamenode_host}},
                           "identity": "nn", "file": "/etc/security/keytabs/nn.service.keytab",
                           "user": "hdfs", "group": "hadoop", "permissions": "400"},
    "NodeManager": {"hosts": {{nm_hosts}},
                    "identity": "nm", "file": "/etc/security/keytabs/nm.service.keytab",
                    "user": "yarn", "group": "hadoop", "permissions": "400"},
    "Oozie Server": {"hosts": {{oozie_server}},
                     "identity": "oozie", "file": "/etc/security/keytabs/oozie.service.keytab",
                     "user": "oozie", "group": "hadoop", "permissions": "400"},
    "ResourceManager": {"hosts": {{rm_host}},
                        "identity": "rm", "file": "/etc/security/keytabs/rm.service.keytab",
                        "user": "yarn", "group": "hadoop", "permissions": "400"},
    "ZooKeeper Server": {"hosts": {{zookeeper_hosts}},
                         "identity": "zookeeper", "file": "/etc/security/keytabs/zk.service.keytab",
                         "user": "zookeeper", "group": "hadoop", "permissions": "400"},
    "App Timeline Server": {"hosts": {{app_timeline_server}},
                            "identity": "yarn", "file": "/etc/security/keytabs/yarn.service.keytab",
                            "user": "yarn", "group": "hadoop", "permissions": "400"},
    "Nagios Server": {"hosts": {{nagios_server}},
                      "identity": "nagios", "file": "/etc/security/keytabs/nagios.service.keytab",
                      "user": "nagios", "group": "hadoop", "permissions": "400"},
    "Falcon SPNEGO User": {"hosts": {{falcon_server}},
                           "identity": "HTTP", "file": "/etc/security/keytabs/spnego.service.keytab",
                           "user": "root", "group": "hadoop", "permissions": "440"},
    "Falcon Server": {"hosts": {{falcon_server}},
                      "identity": "falcon", "file": "/etc/security/keytabs/falcon.service.keytab",
                      "user": "falcon", "group": "hadoop", "permissions": "400"},
    "Knox Gateway": {"hosts": {{knox_server}},
                     "identity": "knox", "file": "/etc/security/keytabs/knox.service.keytab",
                     "user": "knox", "group": "hadoop", "permissions": "400"},
    "Storm UI SPNEGO User": {"hosts": {{storm_ui_server}},
                             "identity": "HTTP", "file": "/etc/security/keytabs/spnego.service.keytab",
                             "user": "root", "group": "hadoop", "permissions": "440"},
    "Storm UI Server": {"hosts": {{storm_ui_server}},
                        "identity": "storm", "file": "/etc/security/keytabs/storm.service.keytab",
                        "user": "storm", "group": "hadoop", "permissions": "400"},
    "DRPC Server": {"hosts": {{storm_drpc_server}},
                    "identity": "nimbus", "file": "/etc/security/keytabs/nimbus.service.keytab",
                    "user": "storm", "group": "hadoop", "permissions": "400"},
    "accumulo Server": {"hosts": {{accumulo_gc_hosts}},
                    "identity": "accumulo", "file": "/etc/security/keytabs/accumulo.service.keytab",
                    "user": "accumulo", "group": "hadoop", "permissions": "400"},
    "ams Server": {"hosts": {{ams_hosts}},
                    "identity": "ams", "file": "/etc/security/keytabs/ams.service.keytab",
                    "user": "ams", "group": "hadoop", "permissions": "400"},
    "ams hbase Server": {"hosts": {{ams_hosts}},
                    "identity": "amshbase", "file": "/etc/security/keytabs/ams-hbase.master.keytab",
                    "user": "ams", "group": "hadoop", "permissions": "400"},
    "ams region Server": {"hosts": {{ams_hosts}},
                    "identity": "amshbase", "file": "/etc/security/keytabs/ams-hbase.regionserver.keytab",
                    "user": "ams", "group": "hadoop", "permissions": "400"},
    "ams zookeper Server": {"hosts": {{ams_hosts}},
                    "identity": "amszk", "file": "/etc/security/keytabs/ams-zk.service.keytab",
                    "user": "ams", "group": "hadoop", "permissions": "400"},
    "atlas Server": {"hosts": {{atlas_hosts}},
                    "identity": "atlas", "file": "/etc/security/keytabs/atlas.service.keytab",
                    "user": "atlas", "group": "hadoop", "permissions": "400"},
    "kafka Server": {"hosts": {{kafka_hosts}},
                    "identity": "kafka", "file": "/etc/security/keytabs/kafka.service.keytab",
                    "user": "kafka", "group": "hadoop", "permissions": "400"}

}""")
# First resolve all templated variables with the cluster_host_info
# Make everything from cluster_host_info into valid json ...
chi_replace = cluster_host_info

for k, v in chi_replace.iteritems():
    if type(v) is set:
        v = list(v)
        chi_replace[k] = v
    if type(v) is str:
        v = [v]
        chi_replace[k] = v
    if type(v) is list:
        v = str(v).replace("'", '"')
        chi_replace[k] = v

service_users = InlineTemplate(service_users, **chi_replace).get_content()
service_users = json.loads(service_users)

ldap_bind_user = default('configurations/freeipa/ldap_bind_user', 'kave_bind_user')
ldap_bind_services = ['twiki', 'gitlab', 'jenkins']


required_users = default('configurations/freeipa/required_users', """{
    "nagios": {"groups": ["hadoop", "nagios"]},
    "hive": {"groups": ["hadoop"]},
    "oozie": {"groups": ["hadoop", "users"]},
    "ambari-qa": {"groups": ["hadoop", "users"]},
    "flume": {"groups": ["hadoop"]},
    "hdfs": {"groups": ["hadoop", "hdfs"]},
    "knox": {"groups": ["hadoop"]},
    "storm": {"groups": ["hadoop"]},
    "mapred": {"groups": ["hadoop"]},
    "atlas": {"groups": ["hadoop"]},
    "accumulo": {"groups": ["hadoop"]},
    "hbase": {"groups": ["hadoop"]},
    "tez": {"groups": ["hadoop", "users"]},
    "zookeeper": {"groups": ["hadoop"]},
    "kafka": {"groups": ["hadoop"]},
    "falcon": {"groups": ["hadoop"]},
    "sqoop": {"groups": ["hadoop"]},
    "yarn": {"groups": ["hadoop"]},
    "hcat": {"groups": ["hadoop"]},
    "dbus": {"comment": "System message bus", "options": ["-d", "/", "-M"]},
    "httpfs": {"comment": "Hadoop HTTPFS", "options": ["-d", "/var/run/hadoop/httpfs", "-M"]},
    "apache": {"comment": "Apache", "options": ["-d", "/var/www", "-M"]},
    "rrdcached": {"comment": "rrdcached", "options": ["-d", "/var/rrdtool/rrdcached", "-M"]},
    "mysql": {"comment": "MySQL Server", "options": ["-d", "/var/lib/mysql", "-M"]}
}""")
required_users = json.loads(required_users)

initial_users_and_groups = default('configurations/freeipa/initial_users_and_groups', '{"Users": [], "Groups" : {}}')
initial_users_and_groups = json.loads(initial_users_and_groups)

initial_user_passwords = default('configurations/freeipa/initial_user_passwords', '{ }')
initial_user_passwords = json.loads(initial_user_passwords)

initial_sudoers = default('configurations/freeipa/initial_sudoers',
                          '{ "Users": [], "Groups":[], "cmdcat": "all", "hostcat": "all", '
                          + '"runasusercat": "all", "runasgroupcat": "all" }')
initial_sudoers = json.loads(initial_sudoers)

kadm5acl_template = default('configurations/freeipa/kadm5acl_template', """*/admin@{{realm}} *
admin@{{realm}} *
admin@{{realm}} a *
admin@{{realm}} i *
admin@{{realm}} x *
admin@{{realm}} m *
""")

resolvconf_template = default('configurations/freeipa/resolvconf_template', """search {{domain}}
nameserver {{ipa_server_ip_address}}
""")

for user, passwd in initial_user_passwords.iteritems():
    if len(passwd) < 8:
        raise ValueError("User : " + user + " cannot be assigned an intital password less than 8 characters")
    else:
        Logger.sensitive_strings[passwd] = "[PROTECTED]"
