import autosar.component
import autosar.rte.base
import cfile as C
from collections import namedtuple


Queue = namedtuple('Queue', "name typename length")

class PortFunction:
   """base class for port functions"""
   def __init__(self, shortname, func):
      self.shortname = shortname
      self.func = func

class ReadPortFunction(PortFunction):
   """port function for Rte_Read actions"""
   def __init__(self, shortname, func, rte_var):
      super().__init__(shortname, func)
      self.rte_var = rte_var

class WritePortFunction(PortFunction):
   """port function for Rte_Write actions"""
   def __init__(self, shortname, func, rte_var):
      super().__init__(shortname, func)
      self.rte_var = rte_var

class SendPortFunction(PortFunction):
   """port function for Rte_Read actions"""
   def __init__(self, shortname, func, rte_var):
      super().__init__(shortname, func)
      self.rte_var = rte_var

class ReceivePortFunction(PortFunction):
   """port function for Rte_Write actions"""
   def __init__(self, shortname, func, rte_var):
      super().__init__(shortname, func)
      self.rte_var = rte_var

class CallPortFunction(PortFunction):
   """port function for Rte_Call actions"""
   def __init__(self, shortname, func):
      super().__init__(shortname, func)

class CalPrmPortFunction(PortFunction):
   """port function for Rte_Call actions"""
   def __init__(self, shortname, func):
      super().__init__(shortname, func)

class ComponentAPI:
   def __init__(self):
      self.read = {}
      self.write = {}
      self.send = {}
      self.receive = {}
      self.mode = {}
      self.call = {}
      self.calprm = {}
      
      self.final = {
                     'read': [],
                     'write': [],
                     'receive': [],
                     'send': [],
                     'mode': [],
                     'call': [],
                     'calprm': [],
                   }

   def finalize(self):      
      if len(self.read)>0:
         self.final['read']=[self.read[k] for k in sorted(self.read.keys())]
      if len(self.write)>0:
         self.final['write']=[self.write[k] for k in sorted(self.write.keys())]
      if len(self.receive)>0:
         self.final['receive']=[self.receive[k] for k in sorted(self.receive.keys())]
      if len(self.mode)>0:
         self.final['receive']=[self.mode[k] for k in sorted(self.mode.keys())]
      if len(self.call)>0:
         self.final['call']=[self.call[k] for k in sorted(self.call.keys())]
      if len(self.calprm)>0:
         self.final['calprm']=[self.calprm[k] for k in sorted(self.calprm.keys())]      
   
   def get_all(self):
      return self.final['read']+self.final['write']+self.final['receive']+self.final['send']+self.final['mode']+self.final['call']+self.final['calprm']
   
   def update(self, other):
      self.read.update(other.read)
      self.write.update(other.write)
      self.send.update(other.send)
      self.receive.update(other.receive)
      self.mode.update(other.mode)
      self.call.update(other.call)
      self.calprm.update(other.calprm)

class Component:
   def __init__(self, swc):
      self.swc = swc
      self.componentAPI = ComponentAPI()
      self.read = {}
      self.write = {}
      self.rteRunnables = {}
      self.autosarRunnables = []

class TimerRunnable:
   """Runnable triggered by timer"""
   def __init__(self, name, symbol, period, canBeInvokedConcurrently = False):
      self.name = name
      self.symbol = symbol
      self.period = period
      self.canBeInvokedConcurrently = canBeInvokedConcurrently
      self.prototype = C.function(self.symbol, 'void')

class OperationInvokeRunnable:
   """Runnable triggered by server invocation"""
   def __init__(self, name, symbol, operation):
      self.name = name
      self.symbol = symbol      
      self.operation = operation
      self.prototype = self._createPrototype()
   
   def _createPrototype(self):
      ws = self.operation.rootWS()
      assert(ws is not None)
      returnType = 'void'
      if len(self.operation.errorRefs)>0:
         returnType = 'Std_ReturnType'
      func = C.function(self.symbol, returnType)
      for argument in self.operation.arguments:
         dataType = ws.find(argument.typeRef)
         if dataType is None:
            raise ValueError('invalid type reference: '+argument.typeRef)
         isPointer = False
         if isinstance(dataType, autosar.datatype.RecordDataType) or isinstance(dataType, autosar.datatype.ArrayDataType) or isinstance(dataType, autosar.datatype.ArrayDataType):
            isPointer = True
         if (isPointer == False) and (argument.direction == 'OUT') or (argument.direction == 'INOUT'):
            isPointer = True
         func.add_arg(C.variable(argument.name, dataType.name, pointer=isPointer))
      return func

class Partition:
   
   def __init__(self, mode='full', prefix='Rte'):
      self.mode = mode #can be single or full
      self.prefix=prefix
      self.components = []
      self.componentAPI = ComponentAPI() #merged API for all components
      self.vars = {}
      self.types = autosar.rte.RteTypeManager()
      self.isFinalized=False
   
   def addComponent(self, swc, runnables = None, name=None):
      """
      adds software component to partition.
      Optional parameters:
      name: Can be used to override name of swc. Default is to use name from swc.
      """
      swc_name = name if name is not None else swc.name
      if isinstance(swc, autosar.component.AtomicSoftwareComponent):
         ws = swc.rootWS()         
         assert(ws is not None)
         component = Component(swc)
         self.components.append(component)         
         if swc.behavior is not None:
            for runnable in swc.behavior.runnables:               
               if runnables is None or runnable.name in runnables:   
                  component.autosarRunnables.append(runnable)                  
            dataElements=set()
            operations=set()
            parameters=set()

            #events
            for event in swc.behavior.events:
               if isinstance(event, autosar.behavior.TimingEvent):
                  runnable = ws.find(event.startOnEventRef)
                  if runnable is None:
                     raise ValueError('invalid reference: '+event.startOnEventRef)
                  if runnables is None or runnable.name in runnables:
                     if runnable.name not in component.rteRunnables:
                        component.rteRunnables[runnable.name] = TimerRunnable(runnable.name, runnable.symbol, event.period, runnable.invokeConcurrently)                         
               elif isinstance(event, autosar.behavior.OperationInvokedEvent):
                  runnable = ws.find(event.startOnEventRef)
                  if runnable is None:
                     raise ValueError('invalid reference: '+event.startOnEventRef)
                  if runnables is None or runnable.name in runnables:
                     if runnable.name not in component.rteRunnables: 
                        iref = event.operationInstanceRef
                        operation = ws.find(iref.operationRef)
                        if operation is None:
                           raise ValueError('invalid reference: '+iref.operationRef)   
                        rte_runnable = OperationInvokeRunnable(runnable.name, runnable.symbol, operation)
                        component.rteRunnables[runnable.name] = rte_runnable
                        for argument in operation.arguments:
                           dataType = ws.find(argument.typeRef)
                        if dataType is None:
                           raise ValueError('invalid type reference: '+argument.typeRef)
                        self.types.processType(ws, dataType)
               elif isinstance(event, autosar.behavior.ModeSwitchEvent):
                  pass #implement later
               else:
                  raise NotImplementedError(type(event))
                     
                  
            #RTE send and call
            for runnable in component.autosarRunnables:
               for dataPoint in runnable.dataReceivePoints+runnable.dataSendPoints:
                  key=(swc.behavior.componentRef, dataPoint.portRef, dataPoint.dataElemRef)
                  dataElements.add(key)
               for callPoint in runnable.serverCallPoints:
                  for elem in callPoint.operationInstanceRefs:
                     key=(swc.behavior.componentRef, elem.portRef, elem.operationRef)
                     operations.add(key)
            
            #parameter ports
            for port in swc.requirePorts:               
               portInterface = ws.find(port.portInterfaceRef)
               if portInterface is not None:
                  if isinstance(portInterface, autosar.portinterface.ParameterInterface):                     
                     for dataElement in portInterface.dataElements:                        
                        key = (swc.ref, port.ref, dataElement.ref)
                        parameters.add(key)
            
            #sender/receiver
            for elem in dataElements:
               (componentRef,portRef,dataElemRef)=elem
               swc=ws.find(componentRef)
               port=ws.find(portRef)
               dataElement = ws.find(dataElemRef)
               if dataElement is None:
                  raise ValueError(dataElemRef)
               typeObj=ws.find(dataElement.typeRef)
               if typeObj is None:
                  raise ValueError('invalid reference: %s'%dataElement.typeRef)
               self.types.processType(ws, typeObj)
               pointer=False           
               ftype=None
               rte_var = None
               if dataElement.name not in self.vars:
                  if len(port.comspec)>0 and (port.comspec[0].initValueRef is not None):                  
                     initValue = ws.find(port.comspec[0].initValueRef)                     
                  rte_var = self._createVar(port, dataElement, typeObj, initValue)                  
               if isinstance(port,autosar.component.RequirePort):
                  if dataElement.isQueued:
                     ftype='Receive'
                  else:
                     ftype='Read'                  
                  pointer=True
               else:
                  if dataElement.isQueued:
                     ftype='Send'                  
                  else:
                     ftype='Write'                  
               assert(ftype is not None)
               if self.mode == 'single':
                  fname='%s_%s_%s_%s_%s'%(self.prefix, ftype, swc_name, port.name, dataElement.name)
               elif self.mode == 'full':
                  fname='%s_%s_%s_%s'%(self.prefix, ftype, port.name, dataElement.name)
               else:
                  raise ValueError('invalid mode value. Valid modes are "full" and "single"')
               shortname='Rte_%s_%s_%s'%(ftype, port.name, dataElement.name)
               typeArg=self._type2arg(typeObj,pointer)
               func=C.function(fname, 'Std_ReturnType')
               func.add_arg(typeArg)               
               if shortname in component.componentAPI.__dict__[ftype.lower()]:
                  raise ValueError('error: %s already defined'%shortname)
               
               rte_port_func = None
               if ftype == 'Read':
                  rte_port_func = ReadPortFunction(shortname, func, rte_var)
               elif ftype == 'Write':
                  rte_port_func = WritePortFunction(shortname, func, rte_var)
               elif ftype == 'Send':
                  rte_port_func = SendPortFunction(shortname, func, rte_var)
               elif ftype == 'Receive':
                  rte_port_func = ReceivePortFunction(shortname, func, rte_var)
               else:
                  raise NotImplementedError(ftype)
               component.componentAPI.__dict__[ftype.lower()][shortname] = rte_port_func
            #client
            for elem in operations:
               (componentRef,portRef,operationRef)=elem
               swc=ws.find(componentRef)
               port=ws.find(portRef)
               operation = ws.find(operationRef)
               if operation is None:
                  raise ValueError('invalid reference: '+operationRef)
               args=[]
               for argument in operation.arguments:
                  typeObj = ws.find(argument.typeRef)
                  pointer = None
                  if isinstance(typeObj, autosar.datatype.RecordDataType) or isinstance(typeObj, autosar.datatype.ArrayDataType):
                     pointer=True
                  else:
                     pointer=False
                  if argument.direction == 'INOUT' or argument.direction=='OUT':
                     pointer=True               
                  self.types.processType(ws, typeObj)
                  args.append(C.variable(argument.name, typeObj.name, pointer=pointer))
               fname='_'.join(['%s_Call'%self.prefix, swc_name, port.name, operation.name])
               shortname='_'.join(['%s_Call'%self.prefix, port.name, operation.name])            
               func=C.function(fname, 'Std_ReturnType', args=args)            
               component.componentAPI.call[shortname]=CallPortFunction(shortname, func)      
            
            #parameters
            for elem in parameters:
               (componentRef,portRef,dataElemRef)=elem
               swc=ws.find(componentRef)
               port=ws.find(portRef)
               dataElement = ws.find(dataElemRef)
               if dataElement is None:
                  raise ValueError(dataElemRef)
               typeObj=ws.find(dataElement.typeRef)
               if typeObj is None:
                  raise ValueError('invalid reference: %s'%dataElement.typeRef)
               self.types.processType(ws, typeObj)
               ftype='Calprm'
               if self.mode == 'single':
                  fname='%s_%s_%s_%s_%s'%(self.prefix, ftype, swc_name, port.name, dataElement.name)
               elif self.mode == 'full':
                  fname='%s_%s_%s_%s'%(self.prefix, ftype, port.name, dataElement.name)
               else:
                  raise ValueError('invalid mode value. Valid modes are "full" and "single"')
               shortname='Rte_%s_%s_%s'%(ftype, port.name, dataElement.name)               
               func=C.function(fname, typeObj.name)               
               if shortname in component.componentAPI.__dict__[ftype.lower()]:
                  raise ValueError('error: %s already defined'%shortname)
               component.componentAPI.__dict__[ftype.lower()][shortname] = CalPrmPortFunction(shortname, func)
            
   def _type2arg(self,typeObj,pointer=False):
      if ( isinstance(typeObj,autosar.datatype.IntegerDataType) or isinstance(typeObj,autosar.datatype.BooleanDataType) ):
         return C.variable('data',typeObj.name,pointer=pointer)
      else:
         pointer=True
         return C.variable('data',typeObj.name,pointer=pointer)
   
   def _createVar(self, port, dataElement, dataType, initValue):
      """
      creates new Variable or Queue object in self.vars map
      """
      name = port.name
      retval = None
      assert(name not in self.vars)      
      if (initValue is not None) and (isinstance(initValue, autosar.constant.Constant)):
         initValue = initValue.value
      if isinstance(dataType, autosar.datatype.BooleanDataType):
         self.vars[name]=autosar.rte.BooleanVariable(name, dataType.name)
      elif isinstance(dataType, autosar.datatype.IntegerDataType):         
         if initValue is not None:
            assert(isinstance(initValue, autosar.constant.IntegerValue))
            initData=str(initValue.value)
         retval = autosar.rte.IntegerVariable(name, dataType.name, initValue=initData)
      elif isinstance(dataType, autosar.datatype.RecordDataType):
         retval = autosar.rte.RecordVariable(name, dataType.name)
      elif isinstance(dataType, autosar.datatype.StringDataType):
         retval = autosar.rte.ArrayVariable(name, dataType.name)         
      else:
         raise NotImplementedError(type(dataType))
      self.vars[name]= retval
      return retval

   def finalize(self):
      if self.isFinalized==False:
         for component in self.components:
            component.componentAPI.finalize()
            self.componentAPI.update(component.componentAPI)
      self.componentAPI.finalize()
      self.isFinalized=True
    