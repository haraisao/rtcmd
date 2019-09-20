#!/usr/bin/env python3
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
import socket
import signal

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

sys.path.append(".")
sys.path.append("rtm")

#####################################################
#
def encodeStr(data):
  return data.encode().decode('unicode_escape')

def decodeStr(data):
  return data.encode('raw-unicode-escape').decode()

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

def isDataInport(prof, dtype):
  try:
    return (prof['port.port_type'] == 'DataInPort' and (dtype == "" or prof['dataport.data_type'] == dtype))
  except:
    return True

def isDataOutport(prof, info):
  try:
    return (prof['port.port_type'] == 'DataOutPort')
  except:
    return True

def format_connection(con):
  res=""
  res+=" %s\n" % con[0].connector_id
  res+="   name: %s\n" % con[0].name
  res+="   ports: %s\n" % con[0].ports
  res+="   properties: [\n" 
  for x in con[0].properties:
    res += "     %s: %s\n" % (x.name, x.value)
  res+="   ]\n" 
  return res
  
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

    self._rtcmd=None
    ########################################

  #
  #
  def __del__(self):
    try:
      if self.manager:
        self.manager.shutdown()
      else:
        self.orb.shutdown(wait_for_completion=CORBA.FALSE)
        self.orb.destroy()
    except:
      pass

  def setRtcmd(self, obj):
    self._rtcmd=obj
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
      name = name.replace("%h", socket.gethostname())
      ref=self.naming.resolveStr(name)
      ref._non_existent()
      return ref._narrow(RTObject)
    except:
      #traceback.print_exc()
      return None

  def wait_for(self, name, timeout=0, func=None, flag=True):
    self.loop=True
    end_time=time.time() + timeout
    if func is None: func = self.resolveRTObject
    while self.loop :
      res=func(name)
      if (not res) == flag:
        if timeout > 0 and time.time() > end_time:
          self.loop=False
        time.sleep(0.3)
      else:
        return True
    return False
  #
  #
  def unbind(self, name):
    try:
      name = name.replace("%h", socket.gethostname())
      self.naming.unbind(name)
      print("Unbind :", name)
      return True
    except:
      return False

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
  def getPorts(self, name, filter=None, f_arg=None):
    res=[]
    if name.count(".rtc") == 0 : name = name+".rtc"
    name = name.replace("%h", socket.gethostname())

    if not (name in self.object_list):
      self.refreshObjectList()

    if name in self.object_list:
      port_ref = self.object_list[name].get_ports()
      for p in port_ref:
        pp = p.get_port_profile()
        pprof =  nvlist2dict(pp.properties)

        if filter is None or filter(pprof, f_arg) :
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
    name = name.replace("%h", socket.gethostname())

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
    name = name.replace("%h", socket.gethostname())

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
  def getAllConnectors(self, name):
    res=[]
    port_ref = self.object_list[name].get_ports()
    for p in port_ref:
      res.append( port_ref.get_connector_profiles() )
    return res

  def disconnectAll(self, name):
    try:
      connectors=self.getAllConnectors(name)
      for con in connectors:
        con.ports[0].disconnect(con.connector_id)
    except:
      print("Error in disconnectAll")
      return False
    return True

  def disconnectAllPorts(self):
    try:
      for name in self._port:
        connectors=self._port[name]._objref.get_connector_profiles()
        for con in connectors:
          con.ports[0].disconnect(con.connector_id)
    except:
      print("Error in disconnectAllPorts")
      return False
    return True
  
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
  def find_connections(self, portname1, portname2):
    try:
      name1, port1 = portname1.split(":")
      name2, port2 = portname2.split(":")
      res=[]
      cons  = self.getConnectors(name1, port1)
      cons2 = self.getConnectors(name2, port2)
      if cons and  cons2 :
        for c in cons:
          for c2 in cons2:
            if c.connector_id == c2.connector_id:
              res.append(c)
      return res
    except:
      traceback.print_exc()
      return None

  #
  #
  def connect(self, portname1, portname2, service=False):
    chk = self.find_connection(portname1, portname2)
    if chk is None:
        return None
    if chk :
       print("Conntction exists:", chk.connector_id)
       return chk.connector_id

    name1, port1 = portname1.split(":")
    name2, port2 = portname2.split(":")
    p1=self.getPortRef(name1, port1)
    p2=self.getPortRef(name2, port2)
    if p1 and p2:
      name='_'.join([name1, port1, name2, port2])
      return self.connect2(name, p1, p2, service)
    else:
      print("Error in connect: No such ports")
    return None
  
  #
  #
  def connect2(self, name, p1, p2, service=False, silent=True):
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
      if not silent :print(res)
      return None
    if not silent :print("connect2", res)
    return prof

  #
  #
  def disconnect(self, portname1, portname2):
    try:
      con=self.find_connection(portname1, portname2)
      if con is None or not con:
        print("No such connrction:", portname1, portname2)
        return False
       
      con.ports[0].disconnect(con.connector_id)
      print("Sucess to disconnect:", portname1, portname2)
      return True
    except:
      print("Fail to disconnect:", portname1, portname2)
      return False

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
  def reset(self, name):
    res=None
    obj=self.resolveRTObject(name)
    if obj :
      ec=obj.get_owned_contexts()[0]
      res=ec.reset_component(obj)
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
  def createInPort(self, name, type=RTC.TimedString, listener=True):
    print("== Create Inport")
    self._datatype[name]=type
    self._data[name] = instantiateDataType(type)
    self._port[name] = OpenRTM_aist.InPort(name, self._data[name])

    if listener:
      self._port[name].addConnectorDataListener(
                            OpenRTM_aist.ConnectorDataListenerType.ON_BUFFER_WRITE,
                            RtcDataListener(name, type, self))

    self._port[name].initConsumers()
    self._port[name].initProviders()
    self._port[name].setConnectionLimit(10)
    #self.registerInPort(name, self._port[name])

  #
  # Create the OutPort of RTC
  #
  def createOutPort(self, name, type=RTC.TimedString):
    print("== Create Outport")
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
  def createDataPort(self, name, dtype, inout, listener=False):
    try:
      if name in self._port: return self._port[name]

      module=dtype.split('.')
      if len(module) > 1 and not module[0] in globals():
        #print("--- load module", module[0])
        exec("import "+module[0], globals())
            
      if inout == 'rtcout':
        self.adaptortype[name] = self.getDataType(dtype)
        self.createOutPort(name, self.adaptortype[name][0])
        self.adaptors[name] = self

      elif inout == 'rtcin':
        self.adaptortype[name] = self.getDataType(dtype)
        self.createInPort(name, self.adaptortype[name][0], listener=listener)
        self.adaptors[name] = self
      else:
        return None

      return self._port[name]
    except:
      return None
  #
  #
  def onData(self, name, data):
    try:
      self._rtcmd.onData(data)
    except:
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
    if sys.version_info.major == 2 and s.count("TimedWString")  : dtype = unicode
    elif s.count("TimedWString"): dtype = str          
    elif s.count("TimedString") : dtype = str
    elif s.count("TimedFloat")  : dtype = float
    elif s.count("TimedDouble") : dtype = float
    elif s.count("TimedShort")  : dtype = int
    elif s.count("TimedLong")   : dtype = int
    elif s.count("TimedOctet")  : dtype = int
    elif s.count("TimedChar")   : dtype = str
    elif s.count("TimedBoolean"): dtype = int
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
  def send(self, name, data, code='utf-8', raw=False, tm=False):
    dtype = self.adaptortype[name][1]
    if raw :
      try:
        if type(data) == str :
          ctm=time.time()
          tm="RTC.Time(%d,%d)" % (int(ctm), int((ctm - int(ctm))*1000000000))
          data=data.replace('{time}', tm)
          self._data[name] = eval(data)
         
        else:
          self._data[name] = data
      except:
        return

      self.writeData(name)
      return

    if self.adaptortype[name][2]:
      ndata = []
      if type(data) == str :
        for d in data.split(","):
          ndata.append( convertDataType(dtype, d, code) )
        self._data[name].data = ndata
      else:
        self._data[name] = data

    elif dtype == str:
      if self._datatype[name] == TimedString:
        self._data[name].data = encodeStr(data)
      else: 
        self._data[name].data = data

    elif sys.version_info.major == 2 and dtype == unicode:
      self._data[name].data = unicode(data)

    elif (dtype == int  or dtype == float) :
      try:
        self._data[name].data = dtype(data)
      except:
        return
    else:
      try:
        if type(data) == str :
          arg=eval(data)
          self._data[name] = dtype(*arg)
        else:
          self._data[name] = data
      except:
        return
    if tm:
      try:
        ctm=time.time()
        self._data[name].tm.sec = int(ctm) 
        self._data[name].tm.nsec = int((ctm - self._data[name].tm.sec) * 1000000000)
      except:
        pass

    self.writeData(name)

  #
  #
  def writeData(self, name, no_thread=True):
    #print("====>",self._data[name])
    try:
      if no_thread:
        return self._port[name].write(self._data[name])
      else:
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

    if self.rtsh:  self.rtsh.setRtcmd(self)
    self.onecycle=once
    self.end=False

    self._info=""
    self.processes = []

    self._error=0
    self._rtc_state=None
    self.loop=False
    self.print_conection=None
    self.print_callback=None
    self.print_formatter=None
  
  #
  #
  def __del__(self):
    self.close()
    if self.rtsh :
      del self.rtsh

  #
  #
  def no_rtsh(self):
    if self.rtsh is None:
      print("No NameService")
      self._error = 1
      return True
    return False

  ###
  #  CPMMAND: list
  def do_list(self, arg):
    if self.no_rtsh() : return self.onecycle
    num=0
    argv=arg.split()
    l_flag=False

    if len(argv) > 0:
      if argv[0] == '-r':
        self.rtsh.refreshObjectList()
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
        if stat == RTC.ACTIVE_STATE:
          comp_name = n[0]+"*"
        elif stat == RTC.ERROR_STATE:
          comp_name = n[0]+"[X]"
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
              print("    [in] ->", port_str, con_str)

            elif typ == "DataOutPort":
              d_typ=pp[1]['dataport.data_type'].split(":")[1]
              port_str = pname+"("+d_typ+")"
              print("    [out]<-", port_str, con_str)

            elif typ == "CorbaPort":
              d_typ=pp[1]['interface_type_name']
              if_dir=pp[1]['interface_polarity']
              port_str = pname+"("+d_typ+")"
              if if_dir == PROVIDED:
                print("     [ P ]=o", port_str, con_str)

              else:  # REQUIRED
                print("     [ C ]=C", port_str, con_str)

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
      self._error = 1
    return [ objname+":"+p+" " for p in completions]

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
    return self.compl_object_name(text, line, begind, endidx, " ")

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
      cons = self.rtsh.find_connections(argv[0], argv[1])
      num=1
      if cons:
        for x in cons:
          print(num, ":", format_connection(cons))
          num += 1
      else:
        print("No connection")
        self._error = 1
    else:
      print("get_connection comp1:p comp2:p")
      self._error = 1
    return self.onecycle

  #
  #
  def complete_get_connection(self, text, line, begind, endidx):
    args=line.split()
    if line[endidx-1] != ' ' and args[-1].find(':') > 0 :
      text=args[-1]
      return self.compl_port_name(text, line, begind, endidx)
    else:
      return self.compl_object_name(text, line, begind, endidx, ":")

  ###
  #  COMMAND: connect
  def do_connect(self, arg):
    if self.no_rtsh() : return self.onecycle

    argv=arg.split()
    if len(argv) > 1:
      res=self.rtsh.connect(argv[0], argv[1])
      if res is None: self._error = 1
    else:
      print("connect comp1:p comp2:p")
      self._error=1
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
      return self.compl_object_name(text, line, begind, endidx, ":")

  #
  #
  def compl_inport_name(self, text, line, begind, endidx, info=""):
    try:
      objname, pname=text.split(':',1)
      if objname:
        if info:
          oname = info.split(":")
          dtype = self.rtsh.getPortDataType(oname[0], oname[1])
        else:
          dtype = info

        ports=self.rtsh.getPorts(objname, isDataInport, dtype)
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
  def compl_outport_name(self, text, line, begind, endidx, sp=" "):
    try:
      objname, pname=text.split(':',1)
      if objname:
        ports=self.rtsh.getPorts(objname, isDataOutport)
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
      return [ objname+":"+p+sp for p in completions]
    else:
      return [ objname+":"+p for p in completions]


  ###
  #  COMMAND: disconnect
  def do_disconnect(self, arg):
    if self.no_rtsh() : return self.onecycle

    argv=arg.split()
    if len(argv) > 1:
      res=self.rtsh.disconnect(argv[0], argv[1])
      if not res: self._error = 1 
    else:
      print("disconnect comp1:p comp2:p")
      self._error = 1
    return self.onecycle

  #
  #
  def complete_disconnect(self, text, line, begind, endidx):
    return self.complete_connect(text, line, begind, endidx)

  ###
  #  COMMAND: activate
  def do_activate(self, arg):
    if self.no_rtsh() : return self.onecycle

    argv=arg.split()
    self.rtsh.getRTObjectList()
    for v in argv:
      objs = self.get_object_names(v)
      for obj in objs:
        res=self.rtsh.activate(obj)
        #if res == RTC.RTC_ERROR: self._error=1
    return self.onecycle

  #
  #
  def complete_activate(self, text, line, begind, endidx):
    return self.compl_object_name(text, line, begind, endidx, " ")

  ###
  #  COMMAND: deactivate
  def do_deactivate(self, arg):
    if self.no_rtsh() : return self.onecycle

    self.rtsh.getRTObjectList()
    argv=arg.split()
    for v in argv:
      objs = self.get_object_names(v)
      for obj in objs:
        res=self.rtsh.deactivate(obj)
        #if res == RTC.RTC_ERROR: self._error=1
    return self.onecycle

  #
  #
  def complete_deactivate(self, text, line, begind, endidx):
    return self.compl_object_name(text, line, begind, endidx, " ")

  ###
  #  COMMAND: get_state
  def do_get_state(self, arg):
    if self.no_rtsh() : return self.onecycle

    stat=self.rtsh.get_component_state(arg)
    print("State:", arg,":", stat)
    self._rtc_state=stat
    return self.onecycle

  #
  #
  def complete_get_state(self, text, line, begind, endidx):
    return self.compl_object_name(text, line, begind, endidx, " ")

  ###
  #  COMMAND: reset
  def do_reset(self, arg):
    if self.no_rtsh() : return self.onecycle

    self.rtsh.getRTObjectList()
    argv=arg.split()
    for v in argv:
      objs = self.get_object_names(v)
      for obj in objs:
        res=self.rtsh.reset(obj)
        if res == RTC.RTC_ERROR: self._error=1
    return self.onecycle
  #
  #
  def complete_reset(self, text, line, begind, endidx):
    return self.compl_object_name(text, line, begind, endidx, " ")

  ###
  #  COMMAND: terminate
  def do_terminate(self, arg):
    if self.no_rtsh() : return self.onecycle

    self.rtsh.getRTObjectList()
    argv=arg.split()
    for v in argv:
      objs = self.get_object_names(v)
      for obj in objs:
        res=self.rtsh.terminate(obj)
        if res == RTC.RTC_ERROR: self._error=1
    return self.onecycle

  #
  #
  def complete_terminate(self, text, line, begind, endidx):
    return self.compl_object_name(text, line, begind, endidx, " ")

  ###
  #  COMMAND: unbind
  def do_unbind(self, arg):
    if self.no_rtsh() : return self.onecycle

    argv=arg.split()
    for v in argv:
      res = self.rtsh.unbind(v)
      if not res: self._error = 1

    return self.onecycle

  def complete_unbind(self, text, line, begind, endidx):
    return self.compl_object_name(text, line, begind, endidx, " ")

  ###
  #  COMMAND: system
  def do_system(self, arg):
    cmdline = arg.split()
    try:
      proc = subprocess.Popen(cmdline, shell=True)
      self.processes.append(proc)
    except:
      traceback.print_exc()
      self._error = 1

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
      self._error = 1

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
 
    return self.onecycle
  ###
  #  COMMAND: launch
  def do_launch(self, arg):
    argv = arg.split(" ")
    verbose=False
    fname=None
    for i in range(len(argv)):
      if argv[i] == "-v":
        verbose=True
      elif fname is None:
        fname = argv[i]
      else:
        pass
  
    if fname is None or not os.path.exists(fname):
      self._error=1
      print("No such file:", fname)
      return self.onecycle

    with open(fname, "r", encoding="utf-8") as f:
      cmds = f.read()
      for cmdline in cmds.split("\n"):
        cmd = cmdline.split("#")[0].strip()
        if cmd :
          if cmd.startswith('print'): cmd = cmdline
          if verbose: print("execute:", cmd)
          self.onecmd(cmd)
          if self._error > 0:
            print("ERROR", self._error)
            return self.onecycle
    self.onecycle

  ###
  #  COMMAND: sleep
  def do_sleep(self, arg):
    time.sleep(int(arg))
    self.onecycle

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

  # ----- record and playback 
  #
  #  COMMAND: record
  def do_record(self, arg):
    self.file = open(arg, "w", encoding="utf-8")
    self.onecycle

  ###
  #  COMMAND: playback
  def do_playback(self, arg):
    self.close()
    with open(arg, "r", encoding="utf-8") as f:
      self.cmdqueue.extend(f.read().splitlines())
    self.onecycle
  #
  #
  def precmd(self, line):
    #line = line.lower()
    self._error = 0
    self._rtc_state=None

    if self.file and 'playback' not in line:
      print(line, file=self.file)
    return line

  #  record and playback -----

  #
  #
  def close(self):
    self.loop=False
    self.rtsh.disconnectAllPorts()
    #if self.print_conection:
    #  self.print_conection[0].disconnect(self.print_conection[1])

    if self.file:
      self.file.close()
      self.file = None

    if self.rtsh and self.rtsh.manager:
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

  # ---------- inject -------
  #
  #  COMMAND: inject
  def do_inject(self, arg):
    if self.no_rtsh() : return self.onecycle
  
    argv=arg.split(" ")
    cname=None
    pname=None
    formatter=None
    nloop=0
    data=""
    intval = 1
    timeout=0
    raw=True

    for i in range(len(argv)):
      if argv[i] == "-m":
        i += 1
        try:
          module="import "+ argv[i]
          exec(module, globals())
        except:
          print("Error in import module")
          pass

      elif argv[i] == "-n":
        i += 1
        try:
          nloop=int(argv[i])
        except:
          print("Invalid options")
          pass
      elif argv[i] == "-r":
        i += 1
        try:
          intval=1.0/float(argv[i])
        except:
          print("Invalid options")
          pass
      elif argv[i] == "-t":
        i += 1
        try:
          timeout=float(argv[i])
        except:
          print("Invalid options")
          pass
      elif argv[i] == "--seat":
        raw=False
      elif argv[i] == "-p":
        i += 1
        try:
          if not (argv[i] in sys.path):
            sys.path.append(argv[i])
        except:
          print("Invalid options")
          pass
      elif argv[i] == "-c":
        i += 1
        data = ' '.join(argv[i:])
        break
      else:
        if argv[i].find(":") > 0 and cname is None:
          cname, pname = argv[i].split(":")
          try:
            pname, formatter = pname.split("#")
          except:
            pass

    dtype = self.rtsh.getPortDataType(cname, pname)
    if dtype :
      dtype2 = dtype.split(":")[1].replace("/", ".")
      pref = self.rtsh.getPortRef(cname, pname)
      #
      # Create inport and connect
      if self.rtsh.manager is None:
        self.rtsh.initRtmManager()
        self.rtsh.refreshObjectList()

      portname = "inject_"+dtype2
      port=self.rtsh.createDataPort(portname, dtype2, "rtcout")
      if port is None:
        print("Fail to create DataPort")
        self._error = 1
        return self.onecycle
      cprof=self.rtsh.connect2(portname+"_"+cname+"_"+pname, port._objref, pref)
      print("=== inject ====")

      #
      # send data
      ctm=time.time()
      if not data.strip() :
        self.loop = True
        count=0
        while self.loop:
          if nloop > 0 and count >= nloop: break
          print("inject ==> ", end="")
          try:
            data=input()
            self.sendData(portname, data, raw)
            count += 1
          except EOFError:
            self.loop = False
            print("")
      else:
        if timeout > 0:
          while True:
            self.sendData(portname, data, raw)
            time.sleep(intval)
            if time.time() > ctm+timeout: break
        else:
          if nloop <= 0: nloop=1
          for i in range(nloop):
            self.sendData(portname, data, raw)
            if i < nloop-1:
              time.sleep(intval)
      
      #
      # disconnect
      port.disconnect(cprof.connector_id)
      #print("-- disconnect inject",self.onecycle)

    return self.onecycle

  #
  #
  def complete_inject(self, text, line, begind, endidx):
    args=line.split()

    if line[endidx-1] != ' ' and args[-1].find(':') > 0 :
      text=args[-1]
      return self.compl_inport_name(text, line, begind, endidx)
    else:
      return self.compl_object_name(text, line, begind, endidx, ":")

  def sendData(self, portname, data, raw=False, tm=True):
    self.rtsh.send(portname, data, raw=raw)

  #
  #
  def do_print(self, arg):
    if self.no_rtsh() : return self.onecycle
    argv=arg.split(" ")
    cname=None
    pname=None
    formatter=None
    nloop=1
    timeout=0
    intval=1
    listener=False
    callback=None

    for i in range(len(argv)):
      if argv[i].startswith("#") : break
      if argv[i] == "-m":
        i += 1
        try:
          module="import "+ argv[i]
          exec(module, globals())
        except:
          print("Error in import module")
          pass
      elif argv[i] == "-n":
        i += 1
        try:
          nloop=int(argv[i])
        except:
          print("Invalid options")
          pass
      elif argv[i] == "-r":
        i += 1
        try:
          intval=1.0/float(argv[i])
        except:
          print("Invalid options")
          pass
      elif argv[i] == "-t":
        i += 1
        try:
          timeout=float(argv[i])
        except:
          print("Invalid options")
          pass
      elif argv[i] == "-p":
        i += 1
        try:
          if not (argv[i] in sys.path):
            sys.path.append(argv[i])
        except:
          print("Invalid options")
          pass
      elif argv[i] == "-l":
        listener=True

      elif argv[i] == "-c":
        i += 1
        try:
          callback=argv[i]
        except:
          print("Invalid options")
          pass
      else:
        if argv[i].find(":") > 0 and cname is None:
          cname, pname = argv[i].split(":")
          try:
            pname, formatter = pname.split("#")
          except:
            try:
              pname, formatter = pname.split("$")
            except:
              pass

    dtype = self.rtsh.getPortDataType(cname, pname)

    if dtype :
      dtype2 = dtype.split(":")[1].replace("/", ".")
      pref = self.rtsh.getPortRef(cname, pname)
      #
      # Create inport and connect
      if self.rtsh.manager is None:
        self.rtsh.initRtmManager()
        self.rtsh.refreshObjectList()

      portname = "print_" + dtype2
      port = self.rtsh.createDataPort(portname, dtype2, "rtcin", listener)
      if port is None:
        print("Fail to create DataPort")
        self._error = 1
        return self.onecycle
      cprof=self.rtsh.connect2(portname+"_"+cname+"_"+pname, port._objref, pref)
      print("=======print:", formatter)
      self.print_formatter=formatter
      try:
        if callback: self.print_callback = eval(callback)
      except:
        pass
      ##############################
      #
      if listener:
        print("Connector_id:", cprof.connector_id)
        self.print_conection=[port, cprof.connector_id]
        pass
      else:
        ctm=time.time()
        if timeout > 0:
          while True:
            if self.rtsh.isNew(portname):
              data = self.rtsh.readData(portname)
            else:
              data=None
            if time.time() > ctm+timeout: break
            # output with formatter
            if data is None:
              print("== No Data")
            else:
              if formatter :
                try:
                  fmt=eval(formatter)
                  print(fmt(data))
                except:
                  print(data)
              else:
                print(data)
            time.sleep(intval)

        else:
          for i in range(nloop):
            #
            # recieve data
            self.loop = True
            while self.loop:
              if self.rtsh.isNew(portname):
                self.loop = False
              time.sleep(0.3)
            data = self.rtsh.readData(portname)

            # output with formatter
            if formatter :
              try:
                fmt=eval(formatter)
                print(fmt(data))
              except:
                print(data)
            else:
              print(data)
        ###########################
        #
        # disconnect
        port.disconnect(cprof.connector_id)
        #print("-- disconnect print",self.onecycle)
      
    #if self.onecycle: self.close()
    return self.onecycle

  #
  #
  def complete_print(self, text, line, begind, endidx):
    args=line.split()

    if line[endidx-1] != ' ' and args[-1].find(':') > 0 :
      text=args[-1]
      return self.compl_outport_name(text, line, begind, endidx, "")
    else:
      return self.compl_object_name(text, line, begind, endidx, ":")

  #
  #
  def do_disconnect_all(self, arg):
    argv = arg.split(" ")
    for name in argv:
      self.rtsh.disconnectAll(name)
    
    return self.onecycle

  def complete_disconnect_all(self, text, line, begind, endidx):
    return self.compl_object_name(text, line, begind, endidx, " ")

  #
  #
  def do_print_exit(self, arg):
    if self.no_rtsh() : return self.onecycle
    if self.print_conection:
      self.print_conection[0].disconnect(self.print_conection[1])
      self.print_conection=None
    return self.onecycle

  #
  #
  def onData(self, data):
    if self.print_callback:
      self.print_callback(data)
    else:
      if self.print_formatter:
        try:
          fmt=eval(self.print_formatter)
          print(fmt(data))
        except:
          print("--format error: ", end="")
          print(data)
      else:
        print(data)

  #
  # COMMAD waite_for
  def do_wait_for(self, arg):
    try:
      if self.no_rtsh() : return self.onecycle
      func=self.find_rtc
      flag=True
      argv=arg.split(" ")
      if len(argv) > 1: timeout=int(argv[1])
      else: timeout=30

      if len(argv) > 2: func=eval(argv[2])
      if len(argv) > 3: flag=eval(argv[3])

      res=self.rtsh.wait_for(argv[0], timeout, func=func, flag=flag)
      if not res:
        print("==== time out =====")
      else:
        print("OK")
    except:
      print("===ERROR===")
    return self.onecycle

  def complete_wait_for(self, text, line, begind, endidx):
    return self.compl_object_name(text, line, begind, endidx, " ")

  def check_active(self, name):
    stat=self.rtsh.get_component_state(name)
    if stat == RTC.ACTIVE_STATE: return True
    else: return False

  def find_rtc(self, name):
    if name.count(".rtc") == 0 : name = name+".rtc"
    stat=self.rtsh.refreshObjectList()
    names=list(self.rtsh.object_list.keys())
    for n in names:
      if n.find(name) >= 0: return True
    return False


def parse_print_args(argv):
  cname=None
  pname=None
  formatter=None
  for i in range(len(argv)):
    if argv[i] == "-m":
      i += 1
      try:
        module="import "+ argv[i]
        exec(module, globals())
      except:
        print("Error in import module")
        pass

    else:
      if argv[i].find(":") > 0:
        cname, pname = argv[i].split(":")
        try:
          pname, formatter = pname.split("#")
        except:
          formatter = None
  return cname, pname, formatter


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

def fmt_TimedString(data):
  res = "Time: %d\n" % (data.tm.sec + data.tm.nsec/10000000000.0)
  res += "Data: %s" % data.data
  return res

####
#   M A I N
def main():
  if not check_process("omniNames") :
    subprocess.Popen(["cmd", "/c", "start", "rtm-naming.bat"])
    time.sleep(2)

  if len(sys.argv) > 1:
    rtcmd=RtCmd(once=True)
    signal.signal(signal.SIGINT, lambda: rtcmd.close())
    rtcmd.onecmd(" ".join(sys.argv[1:]))
    rtcmd.close()
    print(rtcmd._error)
    return 
  else:
    RtCmd().cmdloop(intro="Welcome to RtCmd")
  return 


#########################################################################
#
#  M A I N 
#
if __name__=='__main__':
    main()
