#!/usr/bin/env python
# -*- coding: utf-8 -*-

'''

RtcSh
Copyright (C) 2018
    Isao Hara,AIST,Japan
    All rights reserved.
  Licensed under the MIT License (MIT)
  http://www.opensource.org/licenses/MIT
'''

############### import libraries
from __future__ import print_function
import sys
import os
import time
import signal
import re
import traceback
import subprocess
import platform
import threading

try:
  import readline
except:
  pass
  
import cmd

#########################
from RTC import *
import CosNaming 
from CorbaNaming import *
import SDOPackage
from omniORB import CORBA,URI,any

import OpenRTM_aist
import string

import OpenRTM_aist.CORBA_RTCUtil
import RTC, RTC__POA

#####################################################
#
def check_process(name):
    if platform.system() == "Windows":
        name=os.path.splitext(name)[0] + ".exe"
        proc=subprocess.Popen('tasklist', shell=True, stdout=subprocess.PIPE)
        for line in proc.stdout:
            if line.decode('shift-jis').startswith(name):
                
                return True
    print("===", name, "is not running.")
    return False
#
#
def convertDataType(dtype, data, code='utf-8'):
  if dtype == str:
    if sys.version_info.major == 2:
        return data.encode(code)
    else:
        return data

  elif sys.version_info.major == 2 and dtype == unicode:
    return unicode(data)

  elif dtype == int or dtype == float :
    return dtype(data)
  else:
    if type(data) == str :
        return eval(data)
    return data
#
#
def instantiateDataType(dtype):
  if isinstance(dtype, int) : desc = [dtype]
  elif isinstance(dtype, tuple) : desc = dtype
  else :  desc=omniORB.findType(dtype._NP_RepositoryId) 

  if desc[0] in [ omniORB.tcInternal.tv_alias ]: return instantiateDataType(desc[2])

  if desc[0] in [ omniORB.tcInternal.tv_short, omniORB.tcInternal.tv_long, 
                   omniORB.tcInternal.tv_ushort, omniORB.tcInternal.tv_ulong,
                   omniORB.tcInternal.tv_boolean, omniORB.tcInternal.tv_char,
                   omniORB.tcInternal.tv_octet, omniORB.tcInternal.tv_longlong,
                   omniORB.tcInternal.tv_enum
                  ]: return 0

  if desc[0] in [ omniORB.tcInternal.tv_float, omniORB.tcInternal.tv_double, omniORB.tcInternal.tv_longdouble ]: return 0.0

  if desc[0] in [ omniORB.tcInternal.tv_sequence, omniORB.tcInternal.tv_array,
                  ]: return []

  if desc[0] in [omniORB.tcInternal.tv_string ]: return ""
  if desc[0] in [omniORB.tcInternal.tv_wstring, omniORB.tcInternal.tv_wchar ]: return u""

  if desc[0] == omniORB.tcInternal.tv_struct:
    arg = []
    for i in  range(4, len(desc), 2):
      attr = desc[i]
      attr_type = desc[i+1]
      arg.append(instantiateDataType(attr_type))
    return desc[1](*arg)

  return None


#########################################################################
# DataListener:  This class connected with DataInPort
#
class RtcDataListener(OpenRTM_aist.ConnectorDataListenerT):
    def __init__(self, name, type, obj):
        self._name = name
        self._type = type
        self._obj = obj
        self._ondata_thread=None
    
    def __call__(self, info, cdrdata):
        data = OpenRTM_aist.ConnectorDataListenerT.__call__(self,
                        info, cdrdata, instantiateDataType(self._type))
        self._obj.onData(self._name, data)

###########################################################################
#
#
class Rtc_Sh:
  #
  #
  def __init__(self, orb=None, server_name='localhost'):
    if orb is None:
      self.orb = CORBA.ORB_init(sys.argv)
    else:
      self.orb=orb
    self.name=server_name
    self.naming=CorbaNaming(self.orb, self.name)
    self.maxlen=20
    self.object_list={}
    self.current_ctx=""
    self.manager = None
    #self.getRTObjectList()
    #######################################
    self.adaptors = {}
    self.adaptortype = {}
    self._data = {}
    self._port = {}

    self._consumer = {}
    self._ConsumerPort = {}
    self._ProviderPort = {}
    self._datatype = {}
    self._send_thread = None
    ########################################

  #
  #
  def __del__(self):
    if self.manager:
      self.manager.shutdown()
    else:
      self.orb.shutdown(wait_for_completion=CORBA.FALSE)
      self.orb.destroy()

  #
  #
  def initRtmManager(self):
    if self.orb :
      self.orb.shutdown(wait_for_completion=CORBA.FALSE)
      self.orb.destroy()

    argv=[sys.argv[0]]
    argv.append("-o")
    argv.append("logger.enable:NO")
    argv.append("-o")
    argv.append("manager.shutdown_on_nortcs: NO")
    #argv.append("-o")
    #argv.append("manager.is_master: YES")

    self.manager = OpenRTM_aist.Manager.init(argv)
    self.orb = self.manager._orb
    self.naming=CorbaNaming(self.orb, self.name)

    self.manager.activateManager()
    self.manager.runManager(True)

  #
  #
  def resolveRTObject(self, name):
    try:
      if name.count(".rtc") == 0 : name = name+".rtc"
      ref=self.naming.resolveStr(name)
      ref._non_existent()
      return ref._narrow(RTObject)
    except:
      #traceback.print_exc()
      return None

  #
  #
  def unbind(self, name):
    self.naming.unbind(name)
    print("Unbind :", name)
    return

  #
  #
  def clearObjectList(self):
    self.object_list={}

  #
  #
  def getRTObjectList(self, name_context=None, parent=""):
    res=[]
    if name_context is None:
      name_context = self.naming._rootContext
    binds, bind_i = name_context.list(self.maxlen)
    for bind in binds:
      res = res + self.resolveBindings(bind, name_context, parent)

    if bind_i :
      tl = bind_i.next_n(self.maxlen)
      while tl[0]:
        for bind in tl[1] :
           res = res + self.resolveBindings(bind, name_conext, parent)
        tl = bind_i.next_n(self.maxlen)
    return res

  #
  #
  def resolveBindings(self, bind, name_context, parent):
    res = []
    prefix=parent

    if parent :
      prefix += "/"

    name = prefix + URI.nameToString(bind.binding_name)
    if bind.binding_type == CosNaming.nobject:
      if bind.binding_name[0].kind == "rtc":
        obj = name_context.resolve(bind.binding_name)
        try:
          obj._non_existent()
          obj = obj._narrow(RTObject)
          res = [[name, obj]]
          self.object_list[name] = obj
        except:
          obj = None
          res = [[name, obj]]
      else:
        pass
        #self.object_list[name] = None
    else:
      ctx = name_context.resolve(bind.binding_name)
      ctx = ctx._narrow(CosNaming.NamingContext)
      parent = name
      res = self.getRTObjectList( ctx, parent)
    return res

  #
  #
  def refreshObjectList(self):
    self.object_list = {}
    return self.getRTObjectList()

  #
  #
  def getPorts(self, name):
    res=[]
    if name.count(".rtc") == 0 : name = name+".rtc"
    if not (name in self.object_list):
      self.refreshObjectList()

    if name in self.object_list:
      port_ref = self.object_list[name].get_ports()
      for p in port_ref:
        pp = p.get_port_profile()
        pprof =  nvlist2dict(pp.properties)
        if pp.interfaces:
          ifp=pp.interfaces[0]
          pprof['interface_name'] = ifp.instance_name
          pprof['interface_type_name'] = ifp.type_name
          pprof['interface_polarity'] = ifp.polarity
        res.append( (pp.name, pprof))
    else:
      print("No such RTC:", name)
    return res

  #
  # get DataInPort
  def getInPorts(self, name, info=""):
    res=[]
    dtype=""
    if name.count(".rtc") == 0 : name = name+".rtc"
    if not (name in self.object_list):
      self.refreshObjectList()
    
    if info:
      oname = info.split(":")
      dtype = self.getPortDataType(oname[0], oname[1])
  
    if name in self.object_list:
      port_ref = self.object_list[name].get_ports()
      for p in port_ref:
        pp = p.get_port_profile()
        pprof =  nvlist2dict(pp.properties)

        if pprof['port.port_type'] == 'DataInPort' and (info == "" or pprof['dataport.data_type'] == dtype):
          if pp.interfaces:
            ifp=pp.interfaces[0]
            pprof['interface_name'] = ifp.instance_name
            pprof['interface_type_name'] = ifp.type_name
            pprof['interface_polarity'] = ifp.polarity
          res.append( (pp.name, pprof))
    else:
      print("No such RTC:", name)
    return res

  #
  # get DataOutPort
  def getOutPorts(self, name):
    res=[]
    if name.count(".rtc") == 0 : name = name+".rtc"
    if not (name in self.object_list):
      self.refreshObjectList()

    if name in self.object_list:
      port_ref = self.object_list[name].get_ports()
      for p in port_ref:
        pp = p.get_port_profile()
        pprof =  nvlist2dict(pp.properties)
        if pprof['port.port_type'] == 'DataOutPort' :
          if pp.interfaces:
            ifp=pp.interfaces[0]
            pprof['interface_name'] = ifp.instance_name
            pprof['interface_type_name'] = ifp.type_name
            pprof['interface_polarity'] = ifp.polarity
          res.append( (pp.name, pprof))
    else:
      print("No such RTC:", name)
    return res

  #
  #
  def getPortRef(self, name, port):
    res=[]
    if name in self.object_list:
      self.refreshObjectList()

    if name.count(".rtc") == 0 : name = name+".rtc"

    if name in self.object_list:
      port_ref = self.object_list[name].get_ports()
      for p in port_ref:
        pp = p.get_port_profile()
        if port == pp.name.split('.')[-1]:
          return p
    else:
      print("No such port:", name, ":", port)
    return None

  #
  #
  def getPortDataType(self, name, port):
    res=[]
    if name.count(".rtc") == 0 : name = name+".rtc"
    if not (name in self.object_list):
      self.refreshObjectList()

    if name in self.object_list:
      port_ref = self.object_list[name].get_ports()
      for p in port_ref:
        pp = p.get_port_profile()
        pprof =  nvlist2dict(pp.properties)
        if pp.name.split(".")[1] == port:
          return pprof['dataport.data_type']
    else:
      print("No such RTC:", name)
    return None

  #
  #
  def getConnectors(self, name, port):
    port_ref=self.getPortRef(name, port)
    if port_ref:
      cons = port_ref.get_connector_profiles()
      return cons
    return None
 
  #
  #
  def getConnectionInfo(self, con):
    ports = [(con.ports[0].get_port_profile()).name, (con.ports[1].get_port_profile()).name]
    res={'name': con.name, 'ports': ports, 'id': con.connector_id }
    return res

  #
  #
  def getConnections(self, name, port):
    res = []
    cons = self.getConnectors(name, port)
    if cons:
      for c in cons:
        res.append(self.getConnectionInfo(c))
    return res

  #
  #
  def find_connection(self, portname1, portname2):
    try:
      name1, port1 = portname1.split(":")
      name2, port2 = portname2.split(":")

      #p1=self.getPortRef(name1, port1)
      #p2=self.getPortRef(name2, port2)

      cons  = self.getConnectors(name1, port1)
      cons2 = self.getConnectors(name2, port2)
      if cons and  cons2 :
        for c in cons:
          for c2 in cons2:
            if c.connector_id == c2.connector_id:
              return c
      return False
    except:
      traceback.print_exc()
      return None

  #
  #
  def connect(self, portname1, portname2, service=False):
    if service:
      con_prof = {'port.port_type':'CorbaPort' }
    else:
      con_prof={'dataport.dataflow_type':'push',
              'dataport.interface_type':'corba_cdr' ,
              'dataport.subscription_type':'flush'}

    chk = self.find_connection(portname1, portname2)
    if chk is None:
        return None
    if chk :
       print("Conntction exists:", chk.connector_id)
       return 
    try:
      name1, port1 = portname1.split(":")
      name2, port2 = portname2.split(":")
      p1=self.getPortRef(name1, port1)
      p2=self.getPortRef(name2, port2)
      if p1 and p2:
        name='_'.join([name1, port1, name2, port2])
        prof_req=ConnectorProfile(name, "", [p1, p2], dict2nvlist(con_prof))
        res, prof=p1.connect(prof_req)
      else:
        res="Error in connect"
    except:
      res="Error"
    print(res)
    return
  
  #
  #
  def connect2(self, name, p1, p2, service=False):
    if service:
      con_prof = {'port.port_type':'CorbaPort' }
    else:
      con_prof={'dataport.dataflow_type':'push',
              'dataport.interface_type':'corba_cdr' ,
              'dataport.subscription_type':'flush'}
    try:
      prof_req=ConnectorProfile(name, "", [p1, p2], dict2nvlist(con_prof))
      res, prof=p1.connect(prof_req)
    except:
      res="Error  in connect2"
      print(res)
      return None
    print("connect2", res)
    return prof

  #
  #
  def disconnect(self, portname1, portname2):
    try:
      con=self.find_connection(portname1, portname2)
      if con is None or not con:
        print("No such connrction:", portname1, portname2)
       
      con.ports[0].disconnect(con.connector_id)
      print("Sucess to disconnect:", portname1, portname2)
    except:
      print("Fail to disconnect:", portname1, portname2)

  #
  #
  def getEC(self, name):
    obj=self.resolveRTObject(name)
    if obj :
      ec=obj.get_owned_contexts()[0]
      return ec
    else:
      return None

  #
  #
  def activate(self, name):
    res=None
    obj=self.resolveRTObject(name)
    if obj :
      ec=obj.get_owned_contexts()[0]
      res=ec.activate_component(obj)
    return res

  #
  #
  def deactivate(self, name):
    res=None
    obj=self.resolveRTObject(name)
    if obj :
      ec=obj.get_owned_contexts()[0]
      res=ec.deactivate_component(obj)
    return res

  #
  #
  def get_component_state(self, name):
    stat=None
    obj=self.resolveRTObject(name)
    if obj:
      ec=obj.get_owned_contexts()[0]
      stat=ec.get_component_state(obj)
    return stat

  #
  #
  def terminate(self, name):
    try:
      obj=self.resolveRTObject(name)
    except:
      obj=None
  
    if obj:
      obj.exit()
    return None

  ##############################################
  #
  def createInPort(self, name, type=TimedString, listener=True):
        self._datatype[name]=type
        self._data[name] = instantiateDataType(type)
        self._port[name] = OpenRTM_aist.InPort(name, self._data[name])

        if listener:
          self._port[name].addConnectorDataListener(
                            OpenRTM_aist.ConnectorDataListenerType.ON_BUFFER_WRITE,
                            RtcDataListener(name, type, self))

        #self._port[name].configure()
        self._port[name].initConsumers()
        self._port[name].initProviders()
        self._port[name].setConnectionLimit(10)
        #self.registerInPort(name, self._port[name])

  #
  # Create the OutPort of RTC
  #
  def createOutPort(self, name, type=TimedString):
        self._datatype[name]=type
        self._data[name] = instantiateDataType(type)
        self._port[name] = OpenRTM_aist.OutPort(name, self._data[name],
                                   OpenRTM_aist.RingBuffer(8))

        self._port[name].configure()
        self._port[name].initConsumers()
        self._port[name].initProviders()
        self._port[name].setConnectionLimit(10)
        #self.registerOutPort(name, self._port[name])

  #
  # Create and Register DataPort of RTC
  #
  def createDataPort(self, name, dtype, inout):
        if inout == 'rtcout':
            self.adaptortype[name] = self.getDataType(dtype)
            self.createOutPort(name, self.adaptortype[name][0])
            self.adaptors[name] = self

        elif inout == 'rtcin':
            self.adaptortype[name] = self.getDataType(dtype)
            self.createInPort(name, self.adaptortype[name][0], listener=False)
            self.adaptors[name] = self
        else:
            return False

        return True
  #
  #
  def onData(self, name, data):
    print("===>", name, data)
    return

  #
  #  Get DataType
  #
  def getDataType(self, s):
    if len(s) == 0         : return (TimedString, str, False)
    seq = False

    if s[-3:] == "Seq"     : seq = True

    dtype = str
    if sys.version_info.major == 2 and s.count("WString")  : dtype = unicode
    elif s.count("WString"): dtype = str          
    elif s.count("String") : dtype = str
    elif s.count("Float")  : dtype = float
    elif s.count("Double") : dtype = float
    elif s.count("Short")  : dtype = int
    elif s.count("Long")   : dtype = int
    elif s.count("Octet")  : dtype = int
    elif s.count("Char")   : dtype = str
    elif s.count("Boolean"): dtype = int
    else                   : dtype = eval("%s" % s)

    return (eval("%s" % s), dtype, seq)

    #
    #
  def newData(self,name):
    return instantiateDataType(self._datatype[name])

    #
    #
  def isNew(self,name):
    try:
      return self._port[name].isNew()
    except:
      return False

  #
  # Send Data 
  #
  def send(self, name, data, code='utf-8'):
    dtype = self.adaptortype[name][1]

    if self.adaptortype[name][2]:
      ndata = []
      if type(data) == str :
        for d in data.split(","):
          ndata.append( convertDataType(dtype, d, code) )
        self._data[name].data = ndata
      else:
        self._data[name] = data

    elif dtype == str:
      #self._data[name].data = data.encode(code)
      if self._datatype[name] == TimedString:
        self._data[name].data = data.encode().decode('unicode_escape')
      else: 
        self._data[name].data = data

    elif sys.version_info.major == 2 and dtype == unicode:
      self._data[name].data = unicode(data)

    elif (dtype == int  or dtype == float) and type(data) == dtype:
      try:
        self._data[name].data = dtype(data)
      except:
        return
    else:
      try:
        if type(data) == str :
          self._data[name] = apply(dtype, eval(data))
        else:
          self._data[name] = data
      except:
        return
    self.writeData(name)

  #
  #
  def writeData(self, name):
    try:
      if self._send_thread :
        self._send_thread.join(1)
      self._send_thread=threading.Thread(target=self._port[name].write, name="send_data", args=(self._data[name],))
      self._send_thread.start()
    except:
      pass
  #
  #
  def getData(self,name):
    try:
      return self._data[name]
    except:
      return None

  #
  #
  def readData(self,name):
    try:
      return self._port[name].read()
    except:
      return None

  #
  #
  def readAllData(self,name):
    try:
      res=[]
      while self._port[name].isNew():
        res.append(self._port[name].read())
      return res
    except:
      return []

###############################################
#   cass RtCmd
#
class RtCmd(cmd.Cmd):
  #intro="Welcome to RtCmd"
  prompt="=> "
  file=None

  #
  #
  def __init__(self, rtsh=None, once=False):
    cmd.Cmd.__init__(self)
    if rtsh is None:
      try:
        self.rtsh=Rtc_Sh()
        self.rtsh.getRTObjectList()
      except:
        self.rtsh=None
        print("Error: NameService not found.")
        #os._exit(-1)
    else:
      self.rtsh=rtsh
    self.onecycle=once
    self.end=False

    self._info=""
    self.processes = []

  def __del__(self):
    if self.rtsh :
      del self.rtsh

  def no_rtsh(self):
    if self.rtsh is None:
      print("No NameService")
      return True
    return False

  ###
  #  COMMAND: echo
  def do_echo(self, arg):
    print("Echo:", arg)
    return self.onecycle

  ###
  #  CPMMAND: list
  def do_list(self, arg):
    if self.no_rtsh() : return self.onecycle
    num=0
    argv=arg.split()
    l_flag=False

    if len(argv) > 0:
      if argv[0] == '-r':
        self.rtsh.refreshRTObjectList()
      elif argv[0] == '-l':
        l_flag=True
      else:
        print("Invalid option")
  
    print("===== RTCs =====")
    res = self.rtsh.getRTObjectList()
    for n in res:
      num += 1
      if n[1]:
        stat=self.rtsh.get_component_state(n[0])
        if stat == ACTIVE_STATE:
          comp_name = n[0]+"*"
        else:
          comp_name = n[0]
         
        print(num, ":", comp_name)
        if l_flag:
          ports=self.rtsh.getPorts(n[0])
          for pp in ports:
            pname=pp[0].split('.')[1]
            cons=self.rtsh.getConnectors(n[0], pname)
            typ=pp[1]['port.port_type']
            if cons:
              con_str="\n        +- "+str([ c.name for c in cons])
            else:
              con_str=""

            if typ == "DataInPort":
              d_typ=pp[1]['dataport.data_type'].split(":")[1]
              port_str = pname+"("+d_typ+")"
              print("     <-", port_str, con_str)

            elif typ == "DataOutPort":
              d_typ=pp[1]['dataport.data_type'].split(":")[1]
              port_str = pname+"("+d_typ+")"
              print("     ->", port_str, con_str)

            elif typ == "CorbaPort":
              d_typ=pp[1]['interface_type_name']
              if_dir=pp[1]['interface_polarity']
              port_str = pname+"("+d_typ+")"
              if if_dir == PROVIDED:
                print("     =o", port_str, con_str)

              else:  # REQUIRED
                print("     =C", port_str, con_str)

            else:
              port_str = pname
              print("     --", port_str)

      else:
        print(num, ":[", n[0], "]")
    print("")
    return self.onecycle

  #
  #
  def get_object_names(self, text):
    names=list(self.rtsh.object_list.keys())
    if not text or text == 'all':
      completions=names[:]
    else:
      try:
        completions= [ n for n in names if re.match(text, n) ]
      except:
        pass
    return completions

  #
  #
  def compl_object_name(self, text, line, begind, endidx, sp=""):
    names=list(self.rtsh.object_list.keys())
    if not text:
      completions=names[:]
    else:
      completions= [ n+sp for n in names if n.startswith(text) ]
    return completions 

  #
  #
  def compl_port_name(self, text, line, begind, endidx):
    try:
      objname, pname=text.split(':',1)
      if objname:
        ports=self.rtsh.getPorts(objname)
        pnames=[]
        for pp in ports:
          pnames.append(pp[0].split('.')[1])
        if not pname:
          completions=pnames[:]
        else:
          completions= [ n for n in pnames if n.startswith(pname) ]
      else:
        completions=[]
    except:
      traceback.print_exc()
      completions=[]
    return [ objname+":"+p+" " for p in completions]
    #return completions

  ###
  #  COMMAND: get_ports
  def do_get_ports(self, arg):
    if self.no_rtsh() : return self.onecycle
  
    num=0
    ports = self.rtsh.getPorts(arg)
    print("====== Ports(%s) ======" % arg)
    for pp in ports:
      num += 1
      print(num, ":", pp[0].split('.')[1])
      for k in pp[1]:
         print("   ", k,":", pp[1][k])
            
    print("")
    return self.onecycle

  #
  #
  def complete_get_ports(self, text, line, begind, endidx):
    return self.compl_object_name(text, line, begind, endidx)

  ###
  #  COMMAND: get_connectors
  def do_get_connectors(self, arg):
    if self.no_rtsh() : return self.onecycle

    try:
      name, port = arg.split(":")
      cons=self.rtsh.getConnectors(name, port)
      if cons is None:
        print("   No connectors")
      else:
        for con in cons:
          info=self.rtsh.getConnectionInfo(con)
          print("   ", info['name'],":", info['ports'][0],"==",info['ports'][1])
    except:
      print("Error in get_connectors:", arg)

  #
  #
  def complete_get_connectors(self, text, line, begind, endidx):
    args=line.split()
    if line[endidx-1] != ' ' and args[-1].find(':') > 0 :
      text=args[-1]
      return self.compl_port_name(text, line, begind, endidx)
    else:
      return self.compl_object_name(text, line, begind, endidx)

  ###
  #  COMMAND: get_connection
  def do_get_connection(self, arg):
    if self.no_rtsh() : return self.onecycle

    argv=arg.split()
    if len(argv) > 1:
      cons = self.rtsh.getConnections(argv[0], argv[1])
      num=0
      if cons:
        for x in cons:
          print(num, ":", cons)
          num += 1
      else:
        print("No connection")
    else:
      print("get_connection comp1:p comp2:p")
    return self.onecycle

  #
  #
  def complete_get_connection(self, text, line, begind, endidx):
    args=line.split()
    if line[endidx-1] != ' ' and args[-1].find(':') > 0 :
      text=args[-1]
      return self.compl_port_name(text, line, begind, endidx)
    else:
      return self.compl_object_name(text, line, begind, endidx)

  ###
  #  COMMAND: disconnect
  def do_disconnect(self, arg):
    if self.no_rtsh() : return self.onecycle

    argv=arg.split()
    if len(argv) > 1:
      self.rtsh.disconnect(argv[0], argv[1])
    else:
      print("disconnect comp1:p comp2:p")
    return self.onecycle

  #
  #
  def complete_disconnect(self, text, line, begind, endidx):
    args=line.split()
    if line[endidx-1] != ' ' and args[-1].find(':') > 0 :
      text=args[-1]
      return self.compl_port_name(text, line, begind, endidx)
    else:
      return self.compl_object_name(text, line, begind, endidx)

  ###
  #  COMMAND: connect
  def do_connect(self, arg):
    if self.no_rtsh() : return self.onecycle

    argv=arg.split()
    if len(argv) > 1:
      self.rtsh.connect(argv[0], argv[1])
    else:
      print("connect comp1:p comp2:p")
    return self.onecycle

  #
  #
  def complete_connect(self, text, line, begind, endidx):
    args=line.split()
    try:
      self._info=args[1]
    except:
      self._info=""

    if line[endidx-1] != ' ' and args[-1].find(':') > 0 :
      text=args[-1]
      if(len(args) > 2):
        return self.compl_inport_name(text, line, begind, endidx, self._info)
      else:
        return self.compl_outport_name(text, line, begind, endidx)
    else:
      return self.compl_object_name(text, line, begind, endidx)

  #
  #
  def compl_inport_name(self, text, line, begind, endidx, info=""):
    try:
      objname, pname=text.split(':',1)
      if objname:
        ports=self.rtsh.getInPorts(objname, info)
        pnames=[]
        for pp in ports:
          pnames.append(pp[0].split('.')[1])
        if not pname:
          completions=pnames[:]
        else:
          completions= [ n for n in pnames if n.startswith(pname) ]
      else:
        completions=[]
    except:
      traceback.print_exc()
      completions=[]
    return [ objname+":"+p for p in completions]

  #
  #
  def compl_outport_name(self, text, line, begind, endidx):
    try:
      objname, pname=text.split(':',1)
      if objname:
        ports=self.rtsh.getOutPorts(objname)
        pnames=[]
        for pp in ports:
          pnames.append(pp[0].split('.')[1])
        if not pname:
          completions=pnames[:]
        else:
          completions = [ n for n in pnames if n.startswith(pname) ]
      else:
        completions=[]
    except:
      traceback.print_exc()
      completions=[]
    if len(completions) == 1:
      return [ objname+":"+p+" " for p in completions]
    else:
      return [ objname+":"+p for p in completions]

  ###
  #  COMMAND: activate
  def do_activate(self, arg):
    if self.no_rtsh() : return self.onecycle

    argv=arg.split()
    self.rtsh.getRTObjectList()
    for v in argv:
      objs = self.get_object_names(v)
      for obj in objs:
        self.rtsh.activate(obj)
    return self.onecycle

  #
  #
  def complete_activate(self, text, line, begind, endidx):
    return self.compl_object_name(text, line, begind, endidx)

  ###
  #  COMMAND: deactivate
  def do_deactivate(self, arg):
    if self.no_rtsh() : return self.onecycle

    self.rtsh.getRTObjectList()
    argv=arg.split()
    for v in argv:
      objs = self.get_object_names(v)
      for obj in objs:
        self.rtsh.deactivate(obj)
    return self.onecycle

  #
  #
  def complete_deactivate(self, text, line, begind, endidx):
    return self.compl_object_name(text, line, begind, endidx)

  ###
  #  COMMAND: get_state
  def do_get_state(self, arg):
    if self.no_rtsh() : return self.onecycle

    stat=self.rtsh.get_component_state(arg)
    print("State:", arg,":", stat)
    return self.onecycle

  #
  #
  def complete_get_state(self, text, line, begind, endidx):
    return self.compl_object_name(text, line, begind, endidx)

  ###
  #  COMMAND: terminate
  def do_terminate(self, arg):
    if self.no_rtsh() : return self.onecycle

    self.rtsh.getRTObjectList()
    argv=arg.split()
    for v in argv:
      objs = self.get_object_names(v)
      for obj in objs:
        self.rtsh.terminate(obj)

    return self.onecycle

  #
  #
  def complete_terminate(self, text, line, begind, endidx):
    return self.compl_object_name(text, line, begind, endidx)

  ###
  #  COMMAND: unbind
  def do_unbind(self, arg):
    if self.no_rtsh() : return self.onecycle

    argv=arg.split()
    for v in argv:
      self.rtsh.unbind(v)
    return self.onecycle

  def complete_unbind(self, text, line, begind, endidx):
    return self.compl_object_name(text, line, begind, endidx)

  ###
  #  COMMAND: system
  def do_system(self, arg):
    cmdline = arg.split()
    try:
      proc = subprocess.Popen(cmdline, shell=True)
      self.processes.append(proc)
    except:
      traceback.print_exc()

  ###
  #  COMMAND: start
  def do_start(self, arg):
    arg = "cmd /c start "+arg
    cmdline = arg.split()
    try:
      proc = subprocess.Popen(cmdline, shell=True)
      self.processes.append(proc)
    except:
      traceback.print_exc()

  ###
  #  COMMAND: killall
  def do_killall(self, arg):
    print(self.processes)
    for p in self.processes:
      if p.poll() is None:
        print("--wait--", p)
        p.terminate()
        p.wait(5)

  ###
  #  COMMAND: refresh
  def do_refresh(self,arg):
    if self.rtsh is None:
      print("No NameService")
      return self.onecycle
    self.rtsh.getRTObjectList()

  ###
  #  COMMAND: launch
  def do_launch(self, arg):
    with open(arg, "r") as f:
      cmds = f.read()
      for cmd in cmds.split("\n"):
        cmd = cmd.split("#")[0].strip()
        if cmd :
          self.onecmd(cmd)

  ###
  #  COMMAND: sleep
  def do_sleep(self, arg):
    time.sleep(int(arg))

  ###
  #  COMMAND: bye
  def do_bye(self, arg):
    print('...BYE')
    for p in self.processes:
      if p.poll() is None:
        p.terminate()
        p.wait()
    self.close()
    self.end=True
    return True

  # ----- record and playback -----
  #
  #  COMMAND: record
  def do_record(self, arg):
    self.file = open(arg, 'w')

  ###
  #  COMMAND: playback
  def do_playback(self, arg):
    self.close()
    with open(arg) as f:
      self.cmdqueue.extend(f.read().splitlines())
  #
  #
  def precmd(self, line):
    #line = line.lower()
    if self.file and 'playback' not in line:
      print(line, file=self.file)
    return line

  #
  #
  def close(self):
    if self.file:
      self.file.close()
      self.file = None
    if self.rtsh.manager:
      self.rtsh.manager.shutdown()

  #
  #
  def emptyline(self):
    return

  #
  #
  def completenames(self, text, *ignored):
    dotext = 'do_'+text
    retval = [a[3:]+" " for a in self.get_names() if a.startswith(dotext)]
    return retval

  # ---------- injection -------
  #
  #  COMMAND: injection
  def do_injection(self, arg):
    if self.no_rtsh() : return self.onecycle
  
    argv=arg.split(" ", 1)

    cname, pname =argv[0].split(":")

    dtype = self.rtsh.getPortDataType(cname, pname)
    if dtype :
      dtype2 = dtype.split(":")[1].replace("RTC/", "")
      dtype2 = dtype2.replace("/", ".")
      pref = self.rtsh.getPortRef(cname, pname)
      #
      # Create inport and connect
      if self.rtsh.manager is None: self.rtsh.initRtmManager()

      self.rtsh.createDataPort("injection", dtype2, "rtcout")
      cprof=self.rtsh.connect2("injection_"+cname+"_"+pname, self.rtsh._port["injection"]._objref, pref)

      #
      # send data 
      if len(argv) == 1:
        loop = True
        while loop:
          print("==> ", end="")
          try:
            data=input()
            self.sendData(data)
          except EOFError:
            loop = False
      else:
        self.sendData(argv[1])

      #
      # disconnect
      self.rtsh._port["injection"].disconnect(cprof.connector_id)
      print("-- disconnect injection",self.onecycle)
      
    if self.onecycle: self.close()

    return self.onecycle

  def complete_injection(self, text, line, begind, endidx):
    args=line.split()

    if line[endidx-1] != ' ' and args[-1].find(':') > 0 :
      text=args[-1]
      return self.compl_inport_name(text, line, begind, endidx)
      #return self.compl_outport_name(text, line, begind, endidx)
    else:
      return self.compl_object_name(text, line, begind, endidx)

  def sendData(self, data):
    try:
      self.rtsh.send("injection", eval(data))
    except:
      self.rtsh.send("injection", data)
    return 

  #
  #
  def do_print(self, arg):
    if self.no_rtsh() : return self.onecycle
  
    argv=arg.split(" ", 1)
    cname, pname =argv[0].split(":")
    dtype = self.rtsh.getPortDataType(cname, pname)

    if dtype :
      dtype2 = dtype.split(":")[1].replace("RTC/", "")
      dtype2 = dtype2.replace("/", ".")
      pref = self.rtsh.getPortRef(cname, pname)
      #
      # Create inport and connect
      if self.rtsh.manager is None: self.rtsh.initRtmManager()

      self.rtsh.createDataPort("print", dtype2, "rtcin")
      cprof=self.rtsh.connect2("print_"+cname+"_"+pname, self.rtsh._port["print"]._objref, pref)

      #
      # recieve data
      loop = True
      while loop:
        if self.rtsh.isNew("print"):
          loop = False
        time.sleep(0.3)
      data = self.rtsh.readData("print")
      print(data)
      #
      # disconnect
      self.rtsh._port["print"].disconnect(cprof.connector_id)
      print("-- disconnect print",self.onecycle)
      
    if self.onecycle: self.close()

    return self.onecycle

  #
  #
  def complete_print(self, text, line, begind, endidx):
    args=line.split()

    if line[endidx-1] != ' ' and args[-1].find(':') > 0 :
      text=args[-1]
      return self.compl_outport_name(text, line, begind, endidx)
    else:
      return self.compl_object_name(text, line, begind, endidx)


#########################################
#   Functions
#
def nvlist2dict(nvlist):
  res={}
  for v in nvlist:
    res[v.name] = v.value.value()
  return res

def dict2nvlist(dict) :
  import omniORB.any
  rslt = []
  for tmp in dict.keys() :
    rslt.append(SDOPackage.NameValue(tmp, omniORB.any.to_any(dict[tmp])))
  return rslt

def execute_from_file(fname):
  rtcmd=RtCmd()
  with open(fname, "r") as f:
    cmds = f.read()
    for cmd in cmds.split("\n"):
      rtcmd.onecmd(cmd)

####
#   M A I N
def main():
  if not check_process("omniNames") :
    subprocess.Popen(["cmd", "/c", "start", "rtm-naming.bat"])

  if len(sys.argv) > 1:
    return  RtCmd(once=True).onecmd(" ".join(sys.argv[1:]))
  else:
    RtCmd().cmdloop(intro="Welcome to RtCmd")


#########################################################################
#
#  M A I N 
#
if __name__=='__main__':
    main()
