#!/usr/bin/python
# -*- coding: utf-8 -*-
import re

from backports.functools_lru_cache import lru_cache

from cloudshell.layer_one.core.driver_commands_interface import DriverCommandsInterface
from cloudshell.layer_one.core.response.resource_info.entities.chassis import Chassis
from cloudshell.layer_one.core.response.resource_info.entities.blade import Blade
from cloudshell.layer_one.core.response.resource_info.entities.port import Port
from cloudshell.layer_one.core.response.response_info import ResourceDescriptionResponseInfo
from cloudshell.layer_one.core.response.response_info import GetStateIdResponseInfo
from ixia_visionedge.ixia_nto import NtoApiClient, NtoAuthException


class NtoSession(object):
    MAX_RETRIES = 3

    def __init__(self, address=None, username=None, password=None):
        self._address = address
        self._username = username
        self._password = password

        self._session = None

    def set_login_details(self, address, username, password):
        self._address = address
        self._username = username
        self._password = password

    def _init_session(self):
        if self._address and self._username and self._password:
            return NtoApiClient(self._address, self._username, self._password)
        raise Exception("Login details are not defined")

    @property
    @lru_cache()
    def ifc_cluster(self):
        try:
            cluster_prop = self.getCteCluster()
        except:
            cluster_prop = None

        if cluster_prop:
            return True
        return False

    def _auth_call(self, name):
        """
        Wraps all calls, to check auth
        :param name:
        :return:
        """

        def wrap_func(*args, **kwargs):
            retry = 0
            if not self._session:
                self._session = self._init_session()
            while retry < self.MAX_RETRIES:
                try:
                    return getattr(self._session, name)(*args, **kwargs)
                except NtoAuthException:
                    self._session = self._init_session()
                    retry += 1

        return wrap_func

    def __getattr__(self, item):

        return self._auth_call(item)

    def __del__(self):
        self._session.logout()

    def _normalize_identifier(self, identifier):
        return str(identifier)

    def get_ports(self):
        if self.ifc_cluster:
            return self.getAllCtePorts()
        return self.getAllPorts()

    def get_port_data(self, port_ident):
        port_ident = self._normalize_identifier(port_ident)
        if self.ifc_cluster:
            return self.getCtePort(port_ident)
        return self.getPort(port_ident)

    def modify_port(self, port_ident, request_data):
        port_ident = self._normalize_identifier(port_ident)
        if self.ifc_cluster:
            self.modifyCtePort(port_ident, request_data)
        else:
            self.modifyPort(port_ident, request_data)

    def get_filters(self):
        if self.ifc_cluster:
            return self.getAllCteFilters()
        return self.getAllFilters()

    def get_filter(self, ident):
        ident = self._normalize_identifier(ident)
        if self.ifc_cluster:
            return self.getCteFilter(ident)
        return self.getFilter(ident)

    def create_filter(self, request_data):
        if self.ifc_cluster:
            self.createCteFilter(request_data)
        else:
            self.createFilter(request_data)

    def delete_filter(self, ident):
        ident = self._normalize_identifier(ident)
        if self.ifc_cluster:
            self.deleteCteFilter(ident)
        else:
            self.deleteFilter(ident)


class DriverCommands(DriverCommandsInterface):
    """
    Driver commands implementation
    """

    class _API_KEYS:
        NAME = "name"
        MODE = "mode"
        ENABLED = "enabled"

    class _DEFAULT_KEYS(_API_KEYS):
        IDENTIFIER = "id"
        SRC_PORT_LIST = "source_port_list"
        DST_PORT_LIST = "dest_port_list"
        SRC_FILTER_LIST = "source_filter_list"
        DST_FILTER_LIST = "dest_filter_list"

    class _CLUSTER_KEYS(_API_KEYS):
        IDENTIFIER = "uuid"
        SRC_PORT_LIST = "source_port_uuid_list"
        DST_PORT_LIST = "dest_port_uuid_list"
        SRC_FILTER_LIST = "source_filter_uuid_list"
        DST_FILTER_LIST = "dest_filter_uuid_list"

    class _API_VALUES:
        BIDI = "BIDIRECTIONAL"
        NETWORK = "NETWORK"
        PASS_ALL = "PASS_ALL"
        BLADE_ID = "1"

    def __init__(self, logger, runtime_config):
        """
        :type logger: logging.Logger
        :type runtime_config: cloudshell.layer_one.core.helper.runtime_configuration.RuntimeConfiguration
        """
        self._logger = logger
        self._runtime_config = runtime_config
        # self._ifc_cluster = runtime_config.read_key('IFC_CLUSTER', None)

        # self._KEYS = self._CLUSTER_KEYS if self._ifc_cluster else self._DEFAULT_KEYS
        self._VALUES = self._API_VALUES

        self._nto_session = NtoSession()

    @property
    @lru_cache()
    def _ifc_cluster(self):
        return self._nto_session.ifc_cluster

    @property
    @lru_cache()
    def _KEYS(self):
        return self._CLUSTER_KEYS if self._ifc_cluster else self._DEFAULT_KEYS

    def login(self, address, username, password):
        """
        Perform login operation on the device
        :param address: resource address, "192.168.42.240"
        :param username: username to login on the device
        :param password: password
        :return: None
        :raises Exception: if command failed
        Example:
            # Define session attributes
            self._cli_handler.define_session_attributes(address, username, password)

            # Obtain cli session
            with self._cli_handler.default_mode_service() as session:
                # Executing simple command
                device_info = session.send_command('show version')
                self._logger.info(device_info)
        """
        self._logger.debug('Login')
        self._nto_session.set_login_details(address, username, password)
        self._logger.info('completed log in')

    def get_state_id(self):
        """
        Check if CS synchronized with the device.
        :return: Synchronization ID, GetStateIdResponseInfo(-1) if not used
        :rtype: cloudshell.layer_one.core.response.response_info.GetStateIdResponseInfo
        :raises Exception: if command failed

        Example:
            # Obtain cli session
            with self._cli_handler.default_mode_service() as session:
                # Execute command
                chassis_name = session.send_command('show chassis name')
                return chassis_name
        """
        return GetStateIdResponseInfo(-1)

    def set_state_id(self, state_id):
        """
        Set synchronization state id to the device, called after Autoload or SyncFomDevice commands
        :param state_id: synchronization ID
        :type state_id: str
        :return: None
        :raises Exception: if command failed

        Example:
            # Obtain cli session
            with self._cli_handler.config_mode_service() as session:
                # Execute command
                session.send_command('set chassis name {}'.format(state_id))
        """
        pass

    def map_bidi(self, src_port, dst_port):
        """
        Create a bidirectional connection between source and destination ports
        :param src_port: src port address, '192.168.42.240/1/21'
        :type src_port: str
        :param dst_port: dst port address, '192.168.42.240/1/22'
        :type dst_port: str
        :return: None
        :raises Exception: if command failed

        Example:
            with self._cli_handler.config_mode_service() as session:
                session.send_command('map bidir {0} {1}'.format(convert_port(src_port), convert_port(dst_port)))

        """
        self._logger.info("MapBidi({}<=>{})".format(src_port, dst_port))
        src_port_ident = self._get_port_identifier(self._from_cs_port(src_port))
        dst_port_ident = self._get_port_identifier(self._from_cs_port(dst_port))
        self._enable_port(src_port_ident)
        self._enable_port(dst_port_ident)
        self._create_filter(src_port_ident, dst_port_ident)
        self._create_filter(dst_port_ident, src_port_ident)

    def map_uni(self, src_port, dst_ports):
        """
        Unidirectional mapping of two ports
        :param src_port: src port address, '192.168.42.240/1/21'
        :type src_port: str
        :param dst_ports: list of dst ports addresses, ['192.168.42.240/1/22', '192.168.42.240/1/23']
        :type dst_ports: list
        :return: None
        :raises Exception: if command failed

        Example:
            with self._cli_handler.config_mode_service() as session:
                for dst_port in dst_ports:
                    session.send_command('map {0} also-to {1}'.format(convert_port(src_port), convert_port(dst_port)))
        """
        self._logger.info("MapUni({}->{})".format(src_port, dst_ports))
        src_port_ident = self._get_port_identifier(self._from_cs_port(src_port))
        self._enable_port(src_port_ident)
        for dst_port in dst_ports:
            dst_port_ident = self._get_port_identifier(self._from_cs_port(dst_port))
            self._enable_port(dst_port_ident)
            self._create_filter(src_port_ident, dst_port_ident)

    def get_resource_description(self, address):
        """
        Auto-load function to retrieve all information from the device
        :param address: resource address, '192.168.42.240'
        :type address: str
        :return: resource description
        :rtype: cloudshell.layer_one.core.response.response_info.ResourceDescriptionResponseInfo
        :raises cloudshell.layer_one.core.layer_one_driver_exception.LayerOneDriverException: Layer one exception.

        Example:

            from cloudshell.layer_one.core.response.resource_info.entities.chassis import Chassis
            from cloudshell.layer_one.core.response.resource_info.entities.blade import Blade
            from cloudshell.layer_one.core.response.resource_info.entities.port import Port

            chassis_resource_id = chassis_info.get_id()
            chassis_address = chassis_info.get_address()
            chassis_model_name = "Ixia Visionedge Chassis"
            chassis_serial_number = chassis_info.get_serial_number()
            chassis = Chassis(resource_id, address, model_name, serial_number)

            blade_resource_id = blade_info.get_id()
            blade_model_name = 'Generic L1 Module'
            blade_serial_number = blade_info.get_serial_number()
            blade.set_parent_resource(chassis)

            port_id = port_info.get_id()
            port_serial_number = port_info.get_serial_number()
            port = Port(port_id, 'Generic L1 Port', port_serial_number)
            port.set_parent_resource(blade)

            return ResourceDescriptionResponseInfo([chassis])
        """
        self._logger.info("GetResourceDescriptions")
        chassis_id = "1"
        chassis_model_name = "Ixia Visionedge Chassis"
        chassis = Chassis(chassis_id, address, chassis_model_name)

        blade_table = {}

        port_table = {}
        port_list = self._get_ports()
        if not port_list:
            raise Exception("Ports are not defined.")
        for port_info in port_list:
            port_uuid = port_info.get(self._KEYS.IDENTIFIER)
            port_name = port_info.get(self._KEYS.NAME)
            blade_id, port_id = self._parse_port_name(port_name)
            if blade_id and port_id:
                blade = blade_table.get(blade_id)
                if not blade:
                    blade = Blade(blade_id)
                    blade.set_parent_resource(chassis)
                    blade_table[blade_id] = blade
            else:
                continue
            port = Port(port_id)
            port.set_parent_resource(blade)
            port_table[port_uuid] = port

        filters = self._get_filters()
        for f in filters:
            f_inf = self._get_filter(f.get(self._KEYS.IDENTIFIER))
            src_list = f_inf.get(self._KEYS.SRC_PORT_LIST)
            dst_list = f_inf.get(self._KEYS.DST_PORT_LIST)
            if src_list and dst_list:
                src_port = port_table.get(src_list[0])
                dst_port = port_table.get(dst_list[0])
                if src_port and dst_port:
                    dst_port.add_mapping(src_port)

        return ResourceDescriptionResponseInfo([chassis])

    def map_clear(self, ports):
        """
        Remove simplex/multi-cast/duplex connection ending on the destination port
        :param ports: ports, ['192.168.42.240/1/21', '192.168.42.240/1/22']
        :type ports: list
        :return: None
        :raises Exception: if command failed

        Example:
            exceptions = []
            with self._cli_handler.config_mode_service() as session:
                for port in ports:
                    try:
                        session.send_command('map clear {}'.format(convert_port(port)))
                    except Exception as e:
                        exceptions.append(str(e))
                if exceptions:
                    raise Exception('self.__class__.__name__', ','.join(exceptions))
        """
        self._logger.info("MapClear({})".format(ports))
        for port in ports:
            src_filter_list, dst_filter_list = self._get_port_filters(self._from_cs_port(port))
            if not src_filter_list and not dst_filter_list:
                continue
            map(lambda uuid: self._delete_filter(uuid), src_filter_list + dst_filter_list)

    def map_clear_to(self, src_port, dst_ports):
        """
        Remove simplex/multi-cast/duplex connection ending on the destination port
        :param src_port: src port address, '192.168.42.240/1/21'
        :type src_port: str
        :param dst_ports: list of dst ports addresses, ['192.168.42.240/1/21', '192.168.42.240/1/22']
        :type dst_ports: list
        :return: None
        :raises Exception: if command failed

        Example:
            with self._cli_handler.config_mode_service() as session:
                _src_port = convert_port(src_port)
                for port in dst_ports:
                    _dst_port = convert_port(port)
                    session.send_command('map clear-to {0} {1}'.format(_src_port, _dst_port))
        """

        self._logger.debug("MapClearTo({}->{})".format(src_port, dst_ports))
        src_port_ident = self._get_port_identifier(self._from_cs_port(src_port))
        dst_port_idents = [self._get_port_identifier(self._from_cs_port(port)) for port in dst_ports]

        src_filters, dst_filters = self._get_port_filters(self._from_cs_port(src_port))
        if not dst_filters:
            return
        for filter_uuid in dst_filters:
            src_ports, dst_ports = self._get_filter_ports(filter_uuid)
            if src_port_ident in src_ports and any(uuid in dst_ports for uuid in dst_port_idents):
                self._delete_filter(filter_uuid)

    def get_attribute_value(self, cs_address, attribute_name):
        """
        Retrieve attribute value from the device
        :param cs_address: address, '192.168.42.240/1/21'
        :type cs_address: str
        :param attribute_name: attribute name, "Port Speed"
        :type attribute_name: str
        :return: attribute value
        :rtype: cloudshell.layer_one.core.response.response_info.AttributeValueResponseInfo
        :raises Exception: if command failed

        Example:
            with self._cli_handler.config_mode_service() as session:
                command = AttributeCommandFactory.get_attribute_command(cs_address, attribute_name)
                value = session.send_command(command)
                return AttributeValueResponseInfo(value)
        """
        raise NotImplementedError

    def set_attribute_value(self, cs_address, attribute_name, attribute_value):
        """
        Set attribute value to the device
        :param cs_address: address, '192.168.42.240/1/21'
        :type cs_address: str
        :param attribute_name: attribute name, "Port Speed"
        :type attribute_name: str
        :param attribute_value: value, "10000"
        :type attribute_value: str
        :return: attribute value
        :rtype: cloudshell.layer_one.core.response.response_info.AttributeValueResponseInfo
        :raises Exception: if command failed

        Example:
            with self._cli_handler.config_mode_service() as session:
                command = AttributeCommandFactory.set_attribute_command(cs_address, attribute_name, attribute_value)
                session.send_command(command)
                return AttributeValueResponseInfo(attribute_value)
        """
        raise NotImplementedError

    def map_tap(self, src_port, dst_ports):
        """
        Add TAP connection
        :param src_port: port to monitor '192.168.42.240/1/21'
        :type src_port: str
        :param dst_ports: ['192.168.42.240/1/22', '192.168.42.240/1/23']
        :type dst_ports: list
        :return: None
        :raises Exception: if command failed

        Example:
            return self.map_uni(src_port, dst_ports)
        """
        self._logger.info("MapTap({}->{})".format(src_port, dst_ports))
        self.map_uni(src_port, dst_ports)

    def set_speed_manual(self, src_port, dst_port, speed, duplex):
        """
        Set connection speed. It is not used with new standard
        :param src_port:
        :param dst_port:
        :param speed:
        :param duplex:
        :return:
        """
        raise NotImplementedError

    def _get_ports(self):
        return self._nto_session.get_ports()

    def _parse_port_name(self, port_name):
        blade_id = self._VALUES.BLADE_ID
        port_id = None
        if self._ifc_cluster:
            match = re.match(r'S(\d+)-P(\d+)', port_name, re.IGNORECASE)
            if match:
                blade_id = match.group(1)
                port_id = match.group(2)
        else:
            match = re.match(r'P(\d+)', port_name, re.IGNORECASE)
            if match:
                port_id = match.group(1)

        return blade_id.lstrip("0"), port_id.lstrip("0")

    def _build_port_name(self, blade_id, port_id):
        if self._ifc_cluster:
            return "S{}-P{}".format(blade_id, str(port_id).zfill(2))
        return "P{}".format(str(port_id).zfill(2))

    def _from_cs_port(self, cs_port):
        return self._build_port_name(*cs_port.split("/")[1:])

    def _get_port_data(self, port_ident):
        return self._nto_session.get_port_data(port_ident)

    def _get_port_identifier(self, port_name):
        return self._get_port_data(port_name).get(self._KEYS.IDENTIFIER)

    def _get_port_filters(self, port_ident):
        port_data = self._get_port_data(port_ident)
        src_filters = port_data.get(self._KEYS.SRC_FILTER_LIST)
        dst_filters = port_data.get(self._KEYS.DST_FILTER_LIST)
        return src_filters, dst_filters

    def _enable_port(self, port_ident):
        if not port_ident:
            raise Exception('Port uuid cannot be None')
        request_data = {self._KEYS.MODE: self._VALUES.BIDI, self._KEYS.ENABLED: True}
        self._nto_session.modify_port(port_ident, request_data)

    def _disable_port(self, port_ident):
        request_data = {self._KEYS.MODE: self._VALUES.NETWORK, self._KEYS.ENABLED: False}
        self._nto_session.modify_port(port_ident, request_data)

    def _disable_port_no_filters(self, port_ident):
        src_filters, dst_filters = self._get_port_filters(port_ident)
        if not src_filters and not dst_filters:
            self._disable_port(port_ident)

    def _get_filters(self):
        return self._nto_session.get_filters()

    def _get_filter(self, uuid):
        return self._nto_session.get_filter(uuid)

    def _create_filter(self, src_ident, dst_ident):
        request_data = {self._KEYS.SRC_PORT_LIST: [src_ident],
                        self._KEYS.DST_PORT_LIST: [dst_ident],
                        self._KEYS.MODE: self._VALUES.PASS_ALL}
        self._nto_session.create_filter(request_data)

    def _get_filter_ports(self, filter_uuid):
        filter_data = self._get_filter(filter_uuid)
        src_ports = filter_data.get(self._KEYS.SRC_PORT_LIST)
        dst_ports = filter_data.get(self._KEYS.DST_PORT_LIST)
        return src_ports, dst_ports

    def _delete_filter(self, filter_uuid):
        src_ports, dst_ports = self._get_filter_ports(filter_uuid)
        self._nto_session.delete_filter(filter_uuid)
        map(lambda uuid: self._disable_port_no_filters(uuid), src_ports + dst_ports)
