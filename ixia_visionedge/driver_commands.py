#!/usr/bin/python
# -*- coding: utf-8 -*-
import re

from cloudshell.layer_one.core.driver_commands_interface import DriverCommandsInterface
from cloudshell.layer_one.core.response.resource_info.entities.chassis import Chassis
from cloudshell.layer_one.core.response.resource_info.entities.blade import Blade
from cloudshell.layer_one.core.response.resource_info.entities.port import Port
from cloudshell.layer_one.core.response.response_info import ResourceDescriptionResponseInfo
from cloudshell.layer_one.core.response.response_info import GetStateIdResponseInfo
from ixia_visionedge.ixia_nto import NtoApiClient


class NtoSessionManager(object):
    def __init__(self, address, username, password):
        self._address = address
        self._username = username
        self._password = password
        self.session = None

    def __enter__(self, ):
        self.session = NtoApiClient(self._address, self._username, self._password)
        return self.session

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.session.logout()


class DriverCommands(DriverCommandsInterface):
    """
    Driver commands implementation
    """

    class API:
        class KEY:
            UUID = "uuid"
            NAME = "name"
            MODE = "mode"
            ENABLED = "enabled"
            SRC_PORT_UUID_LIST = "source_port_uuid_list"
            DST_PORT_UUID_LIST = "dest_port_uuid_list"
            SRC_FILTER_UUID_LIST = "source_filter_uuid_list"
            DST_FILTER_UUID_LIST = "dest_filter_uuid_list"

        class VALUE:
            BIDI = "BIDIRECTIONAL"
            NETWORK = "NETWORK"
            PASS_ALL = "PASS_ALL"

    def __init__(self, logger, runtime_config):
        """
        :type logger: logging.Logger
        :type runtime_config: cloudshell.layer_one.core.helper.runtime_configuration.RuntimeConfiguration
        """
        self._logger = logger
        self._runtime_config = runtime_config
        self._login_details = None

    @property
    def _nto_session_manager(self):
        if self._login_details:
            return NtoSessionManager(*self._login_details)
        raise Exception("Login details are not defined")

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

        # self._nto_session.logout()
        self._login_details = [address, username, password]
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
        with self._nto_session_manager as nto_session:
            src_port_uuid = nto_session.getCtePort(self._from_cs_port(src_port)).get(self.API.KEY.UUID)
            dst_port_uuid = nto_session.getCtePort(self._from_cs_port(dst_port)).get(self.API.KEY.UUID)
            self._enable_port(src_port_uuid, nto_session)
            self._enable_port(dst_port_uuid, nto_session)
            self._create_filter(src_port_uuid, dst_port_uuid, nto_session)
            self._create_filter(dst_port_uuid, src_port_uuid, nto_session)

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
        with self._nto_session_manager as nto_session:
            src_port_uuid = nto_session.getCtePort(self._from_cs_port(src_port)).get(self.API.KEY.UUID)
            self._enable_port(src_port_uuid, nto_session)
            for dst_port in dst_ports:
                dst_port_uuid = nto_session.getCtePort(self._from_cs_port(dst_port)).get(self.API.KEY.UUID)
                self._enable_port(dst_port_uuid, nto_session)
                self._create_filter(src_port_uuid, dst_port_uuid, nto_session)

    @staticmethod
    def _parse_port_name(port_name):
        match = re.match(r'S(\d+)-P(\d+)', port_name, re.IGNORECASE)
        if match:
            blade_id = match.group(1)
            port_id = match.group(2)
            return blade_id, port_id

    @staticmethod
    def _build_port_name(blade_id, port_id):
        return "S{}-P{}".format(blade_id, str(port_id).zfill(2))

    def _from_cs_port(self, cs_port):
        return self._build_port_name(*cs_port.split("/")[1:])

    def _enable_port(self, port_uuid, nto_session):
        if not port_uuid:
            raise Exception('Port uuid cannot be None')
        nto_session.modifyCtePort(port_uuid, {self.API.KEY.MODE: self.API.VALUE.BIDI, self.API.KEY.ENABLED: True})

    def _disable_port(self, port_uuid, nto_session):
        nto_session.modifyCtePort(port_uuid,
                                  {self.API.KEY.MODE: self.API.VALUE.NETWORK, self.API.KEY.ENABLED: False})

    def _disable_port_no_filters(self, port_uuid, nto_session):
        port_data = nto_session.getCtePort(port_uuid)
        if not port_data.get(self.API.KEY.SRC_FILTER_UUID_LIST) and not port_data.get(
                self.API.KEY.DST_FILTER_UUID_LIST):
            self._disable_port(port_uuid, nto_session)

    def _create_filter(self, src_uuid, dst_uuid, nto_session):
        nto_session.createCteFilter(
            {self.API.KEY.SRC_PORT_UUID_LIST: [src_uuid],
             self.API.KEY.DST_PORT_UUID_LIST: [dst_uuid],
             self.API.KEY.MODE: self.API.VALUE.PASS_ALL})

    def _delete_filter(self, filter_uuid, nto_session):
        filter_data = nto_session.getCteFilter(filter_uuid)
        filter_src_ports = filter_data.get(self.API.KEY.SRC_PORT_UUID_LIST)
        filter_dst_ports = filter_data.get(self.API.KEY.DST_PORT_UUID_LIST)
        nto_session.deleteCteFilter(filter_uuid)
        map(lambda uuid: self._disable_port_no_filters(uuid, nto_session), filter_src_ports + filter_dst_ports)

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
        with self._nto_session_manager as nto_session:
            chassis_id = "1"
            chassis_model_name = "Ixia Visionedge Chassis"
            chassis = Chassis(chassis_id, address, chassis_model_name)

            blade_table = {}

            port_table = {}
            port_list = nto_session.getAllCtePorts()
            if not port_list:
                raise Exception("Ports are not defined.")
            for port_info in port_list:
                port_uuid = port_info.get(self.API.KEY.UUID)
                port_name = port_info.get(self.API.KEY.NAME)
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

            filters = nto_session.getAllCteFilters()
            for f in filters:
                f_inf = nto_session.getCteFilter(f.get(self.API.KEY.UUID))
                src_list = f_inf.get(self.API.KEY.SRC_PORT_UUID_LIST)
                dst_list = f_inf.get(self.API.KEY.DST_PORT_UUID_LIST)
                src_id = src_list[0] if src_list else None
                dst_id = dst_list[0] if dst_list else None
                if src_id and dst_id:
                    src_port = port_table.get(src_id)
                    dst_port = port_table.get(dst_id)
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
        with self._nto_session_manager as nto_session:
            for port in ports:
                port_data = nto_session.getCtePort(self._from_cs_port(port))
                src_filter_list = port_data.get(self.API.KEY.SRC_FILTER_UUID_LIST)
                dst_filter_list = port_data.get(self.API.KEY.DST_FILTER_UUID_LIST)
                if not src_filter_list and not dst_filter_list:
                    continue
                map(lambda uuid: self._delete_filter(uuid, nto_session), src_filter_list + dst_filter_list)

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
        with self._nto_session_manager as nto_session:
            src_port_data = nto_session.getCtePort(self._from_cs_port(src_port))
            src_port_uuid = src_port_data.get(self.API.KEY.UUID)
            dst_port_uuids = [nto_session.getCtePort(self._from_cs_port(port)).get(self.API.KEY.UUID) for port in
                              dst_ports]

            filter_uuid_list = src_port_data.get(self.API.KEY.DST_FILTER_UUID_LIST)
            if not filter_uuid_list:
                return
            for filter_uuid in filter_uuid_list:
                filter_data = nto_session.getCteFilter(filter_uuid)
                filter_src_ports = filter_data.get(self.API.KEY.SRC_PORT_UUID_LIST)
                filter_dst_ports = filter_data.get(self.API.KEY.DST_PORT_UUID_LIST)
                if src_port_uuid in filter_src_ports and any(uuid in filter_dst_ports for uuid in dst_port_uuids):
                    self._delete_filter(filter_uuid, nto_session)

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
