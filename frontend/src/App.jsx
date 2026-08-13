import React, { useState, useEffect, useRef } from 'react';
import { 
  Activity, 
  Layers, 
  Server, 
  AlertTriangle, 
  ShieldCheck, 
  RefreshCw, 
  Play, 
  Plus, 
  Edit3, 
  Trash2, 
  CheckCircle, 
  XCircle, 
  Clock, 
  Info,
  ChevronRight,
  Wifi,
  WifiOff,
  Settings,
  HardDrive,
  Terminal,
  User,
  Mail,
  Lock,
  UserPlus
} from 'lucide-react';

const BACKEND_URL = 'http://localhost:8000';

function App() {
  // Authentication & Session States
  const [token, setToken] = useState(localStorage.getItem('netvision_token') || '');
  const [user, setUser] = useState(() => {
    try {
      const stored = localStorage.getItem('netvision_user');
      return stored ? JSON.parse(stored) : null;
    } catch {
      return null;
    }
  });
  const [authLoading, setAuthLoading] = useState(false);
  const [loginUsername, setLoginUsername] = useState('');
  const [loginPassword, setLoginPassword] = useState('');
  const [loginError, setLoginError] = useState(null);

  // User Management States
  const [usersList, setUsersList] = useState([]);
  const [usersLoading, setUsersLoading] = useState(false);
  const [showAddUserModal, setShowAddUserModal] = useState(false);
  const [showEditUserModal, setShowEditUserModal] = useState(false);
  const [selectedUser, setSelectedUser] = useState(null);
  const [userFormData, setUserFormData] = useState({
    email: '',
    username: '',
    password: '',
    full_name: '',
    role: 'VIEWER',
    is_active: true
  });

  const authFetch = async (url, options = {}) => {
    const headers = {
      ...options.headers,
    };
    const currentToken = localStorage.getItem('netvision_token') || token;
    if (currentToken) {
      headers['Authorization'] = `Bearer ${currentToken}`;
    }
    
    let body = options.body;
    if (body && typeof body === 'object' && !(body instanceof FormData)) {
      headers['Content-Type'] = 'application/json';
      body = JSON.stringify(body);
    }
    
    const res = await fetch(url, {
      ...options,
      headers,
      body
    });
    
    if (res.status === 401) {
      handleLogout();
      throw new Error("Session expired. Please log in again.");
    }
    return res;
  };

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoginError(null);
    setAuthLoading(true);
    try {
      const response = await fetch(`${BACKEND_URL}/api/v1/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username_or_email: loginUsername,
          password: loginPassword
        })
      });
      
      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || "Authentication failed");
      }
      
      const data = await response.json();
      localStorage.setItem('netvision_token', data.access_token);
      localStorage.setItem('netvision_user', JSON.stringify(data.user));
      setToken(data.access_token);
      setUser(data.user);
      setLoginUsername('');
      setLoginPassword('');
      showToast(`Welcome back, ${data.user.full_name || data.user.username}!`);
    } catch (err) {
      setLoginError(err.message);
    } finally {
      setAuthLoading(false);
    }
  };

  const handleLogout = async () => {
    try {
      const currentToken = localStorage.getItem('netvision_token') || token;
      if (currentToken) {
        await fetch(`${BACKEND_URL}/api/v1/auth/logout`, {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${currentToken}` }
        });
      }
    } catch (err) {
      console.error("Logout endpoint call failed:", err);
    } finally {
      localStorage.removeItem('netvision_token');
      localStorage.removeItem('netvision_user');
      setToken('');
      setUser(null);
      setActiveTab('overview');
    }
  };

  const isAdmin = user?.role === 'ADMIN';
  const isOperator = user?.role === 'OPERATOR';
  const isViewer = user?.role === 'VIEWER';
  const hasOperatorRights = isAdmin || isOperator;
  const hasAdminRights = isAdmin;

  const fetchUsers = async () => {
    setUsersLoading(true);
    try {
      const response = await authFetch(`${BACKEND_URL}/api/v1/users`);
      if (!response.ok) {
        const errDetails = await response.json();
        throw new Error(errDetails.detail || "Failed to load user accounts");
      }
      const data = await response.json();
      setUsersList(data);
    } catch (err) {
      showToast(err.message, false);
    } finally {
      setUsersLoading(false);
    }
  };

  const handleAddUserSubmit = async (e) => {
    e.preventDefault();
    try {
      const response = await authFetch(`${BACKEND_URL}/api/v1/users`, {
        method: 'POST',
        body: userFormData
      });
      if (!response.ok) {
        const errDetails = await response.json();
        throw new Error(errDetails.detail || "Failed to create user");
      }
      showToast("User account registered successfully!");
      setShowAddUserModal(false);
      resetUserForm();
      fetchUsers();
    } catch (err) {
      showToast(err.message, false);
    }
  };

  const handleEditUserSubmit = async (e) => {
    e.preventDefault();
    const payload = {
      email: userFormData.email,
      username: userFormData.username || null,
      full_name: userFormData.full_name || null,
      role: userFormData.role,
      is_active: userFormData.is_active
    };
    if (userFormData.password) {
      payload.password = userFormData.password;
    }
    
    try {
      const response = await authFetch(`${BACKEND_URL}/api/v1/users/${selectedUser.id}`, {
        method: 'PUT',
        body: payload
      });
      if (!response.ok) {
        const errDetails = await response.json();
        throw new Error(errDetails.detail || "Failed to update user");
      }
      showToast("User account settings updated!");
      setShowEditUserModal(false);
      resetUserForm();
      fetchUsers();
      
      const updated = await response.json();
      if (updated.id === user?.id) {
        localStorage.setItem('netvision_user', JSON.stringify(updated));
        setUser(updated);
      }
    } catch (err) {
      showToast(err.message, false);
    }
  };

  const handleDeleteUser = async (targetUser) => {
    if (targetUser.id === user?.id) {
      showToast("You cannot delete your own administrative account.", false);
      return;
    }
    if (!window.confirm(`Are you sure you want to permanently delete user ${targetUser.username || targetUser.email}?`)) return;
    try {
      const response = await authFetch(`${BACKEND_URL}/api/v1/users/${targetUser.id}`, {
        method: 'DELETE'
      });
      if (!response.ok) {
        const errDetails = await response.json();
        throw new Error(errDetails.detail || "Failed to delete user");
      }
      showToast("User account deleted.");
      fetchUsers();
    } catch (err) {
      showToast(err.message, false);
    }
  };

  const openEditUserModal = (targetUser) => {
    setSelectedUser(targetUser);
    setUserFormData({
      email: targetUser.email,
      username: targetUser.username || '',
      password: '',
      full_name: targetUser.full_name || '',
      role: targetUser.role,
      is_active: targetUser.is_active
    });
    setShowEditUserModal(true);
  };
  
  const resetUserForm = () => {
    setUserFormData({
      email: '',
      username: '',
      password: '',
      full_name: '',
      role: 'VIEWER',
      is_active: true
    });
    setSelectedUser(null);
  };

  // Navigation & UI States
  const [activeTab, setActiveTab] = useState('overview');
  const [devices, setDevices] = useState([]);
  const [recentLogs, setRecentLogs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [countdown, setCountdown] = useState(10);
  
  // Modal States
  const [showAddModal, setShowAddModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [showDetailsModal, setShowDetailsModal] = useState(false);
  const [selectedDevice, setSelectedDevice] = useState(null);
  const [detailsDevice, setDetailsDevice] = useState(null);

  // Refs to avoid stale closures in interval
  const detailsDeviceRef = useRef(detailsDevice);
  const showDetailsModalRef = useRef(showDetailsModal);

  // Sync refs on render
  detailsDeviceRef.current = detailsDevice;
  showDetailsModalRef.current = showDetailsModal;
  
  // TCP Port Status States
  const [devicePortsStatus, setDevicePortsStatus] = useState([]);
  const [checkingPorts, setCheckingPorts] = useState(false);
  const [portConfigInput, setPortConfigInput] = useState('');

  // SNMP States
  const [snmpStatus, setSnmpStatus] = useState(null);
  const [snmpSystem, setSnmpSystem] = useState(null);
  const [snmpInterfaces, setSnmpInterfaces] = useState([]);
  const [snmpLoading, setSnmpLoading] = useState(false);
  const [snmpError, setSnmpError] = useState(null);

  // Form States
  const [formData, setFormData] = useState({
    name: '',
    hostname: '',
    ip_address: '',
    device_type: 'server',
    description: '',
    monitoring_enabled: true,
    ping_interval: 30,
    tcp_ports: '',
    snmp_enabled: false,
    snmp_version: 'v2c',
    snmp_community: 'public',
    snmp_port: 161,
    snmp_polling_interval: 30
  });

  // Action/Trigger States
  const [pingingId, setPingingId] = useState(null);
  const [manualPingResult, setManualPingResult] = useState(null);
  const [successMessage, setSuccessMessage] = useState(null);
  const [errorMessage, setErrorMessage] = useState(null);

  // Alert Center States
  const [alerts, setAlerts] = useState([]);
  const [alertSummary, setAlertSummary] = useState({
    total_active: 0,
    critical: 0,
    warning: 0,
    acknowledged: 0,
    resolved: 0
  });
  const [alertSettings, setAlertSettings] = useState({
    icmp_latency_warning: 200,
    icmp_latency_critical: 500,
    packet_loss_warning: 10,
    packet_loss_critical: 30,
    snmp_traffic_warning_bps: 80000000
  });
  const [alertFilters, setAlertFilters] = useState({
    status: 'ACTIVE', // 'ACTIVE', 'OPEN', 'ACKNOWLEDGED', 'RESOLVED', 'ALL'
    severity: 'ALL', // 'ALL', 'CRITICAL', 'WARNING', 'INFO'
  });
  const [showSettingsPanel, setShowSettingsPanel] = useState(false);
  const [isSavingSettings, setIsSavingSettings] = useState(false);

  // Fetch alerts and settings
  const fetchAlertsInfo = async () => {
    try {
      const [alertsRes, summaryRes, settingsRes] = await Promise.all([
        authFetch(`${BACKEND_URL}/api/v1/alerts/`),
        authFetch(`${BACKEND_URL}/api/v1/alerts/summary`),
        authFetch(`${BACKEND_URL}/api/v1/alerts/settings`)
      ]);
      
      if (alertsRes.ok) {
        const data = await alertsRes.json();
        setAlerts(data);
      }
      if (summaryRes.ok) {
        const data = await summaryRes.json();
        setAlertSummary(data);
      }
      if (settingsRes.ok) {
        const data = await settingsRes.json();
        setAlertSettings(data);
      }
    } catch (err) {
      console.error("Failed to fetch alerts info:", err);
    }
  };

  const handleAcknowledgeAlert = async (alertId) => {
    try {
      const response = await authFetch(`${BACKEND_URL}/api/v1/alerts/${alertId}/acknowledge`, {
        method: 'POST'
      });
      if (!response.ok) throw new Error("Failed to acknowledge alert");
      showToast("Alert acknowledged successfully!");
      fetchAlertsInfo();
    } catch (err) {
      showToast(err.message, false);
    }
  };

  const handleResolveAlert = async (alertId) => {
    try {
      const response = await authFetch(`${BACKEND_URL}/api/v1/alerts/${alertId}/resolve`, {
        method: 'POST'
      });
      if (!response.ok) throw new Error("Failed to resolve alert");
      showToast("Alert resolved successfully!");
      fetchAlertsInfo();
    } catch (err) {
      showToast(err.message, false);
    }
  };

  const handleSaveAlertSettings = async (e) => {
    e.preventDefault();
    setIsSavingSettings(true);
    try {
      const response = await authFetch(`${BACKEND_URL}/api/v1/alerts/settings`, {
        method: 'PUT',
        body: alertSettings
      });
      if (!response.ok) throw new Error("Failed to update threshold settings");
      const data = await response.json();
      setAlertSettings(data);
      showToast("Threshold settings saved successfully!");
      setShowSettingsPanel(false);
    } catch (err) {
      showToast(err.message, false);
    } finally {
      setIsSavingSettings(false);
    }
  };

  // Fetch all devices from database
  const fetchDevices = async () => {
    try {
      const response = await authFetch(`${BACKEND_URL}/api/v1/devices/`);
      if (!response.ok) throw new Error("Failed to fetch devices");
      const data = await response.json();
      // Sort devices deterministically by name to prevent layout jumping/reordering
      const sortedData = [...data].sort((a, b) => a.name.localeCompare(b.name));
      setDevices(sortedData);
      
      // Refresh alert states
      fetchAlertsInfo();
      
      // Pull recent logs for the overview table for each device
      const logsPromises = data.map(device => 
        authFetch(`${BACKEND_URL}/api/v1/devices/${device.id}/metrics?limit=5`)
          .then(res => res.ok ? res.json() : [])
          .catch(() => [])
      );
      const allLogs = await Promise.all(logsPromises);
      // Flatten and sort by timestamp
      const flatLogs = allLogs.flat().sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
      setRecentLogs(flatLogs.slice(0, 20));

      // If details modal is open, refresh detailsDevice state as well
      if (detailsDeviceRef.current) {
        const updated = data.find(d => d.id === detailsDeviceRef.current.id);
        if (updated) {
          setDetailsDevice(updated);
        }
      }
    } catch (err) {
      console.error(err);
      setErrorMessage("Error communicating with NetVision API backend.");
    }
  };

  // Fetch latest TCP port statuses
  const fetchDevicePortsStatus = async (deviceId) => {
    try {
      const response = await authFetch(`${BACKEND_URL}/api/v1/devices/${deviceId}/ports`);
      if (response.ok) {
        const data = await response.json();
        setDevicePortsStatus(data);
      }
    } catch (err) {
      console.error("Failed to fetch port status:", err);
    }
  };

  // Trigger manual port check (POST /ports/check)
  const handleCheckPortsNow = async (deviceId) => {
    setCheckingPorts(true);
    try {
      const response = await authFetch(`${BACKEND_URL}/api/v1/devices/${deviceId}/ports/check`, {
        method: 'POST'
      });
      if (!response.ok) throw new Error("Port check request failed.");
      showToast("TCP Port diagnostics complete!");
      await fetchDevicePortsStatus(deviceId);
    } catch (err) {
      showToast(err.message, false);
    } finally {
      setCheckingPorts(false);
    }
  };

  // Fetch SNMP info for a device
  const fetchSnmpData = async (deviceId) => {
    setSnmpLoading(true);
    setSnmpError(null);
    try {
      const [statusRes, sysRes, ifRes] = await Promise.all([
        authFetch(`${BACKEND_URL}/api/v1/devices/${deviceId}/snmp/status`),
        authFetch(`${BACKEND_URL}/api/v1/devices/${deviceId}/snmp/system`),
        authFetch(`${BACKEND_URL}/api/v1/devices/${deviceId}/snmp/interfaces`)
      ]);

      if (statusRes.ok) {
        const statusData = await statusRes.json();
        setSnmpStatus(statusData);
        if (!statusData.working && statusData.error_msg) {
          setSnmpError(statusData.error_msg);
        }
      }
      if (sysRes.ok) {
        const sysData = await sysRes.json();
        setSnmpSystem(sysData);
      }
      if (ifRes.ok) {
        const ifData = await ifRes.json();
        setSnmpInterfaces(ifData);
      }
    } catch (err) {
      console.error("Failed to fetch SNMP data:", err);
      setSnmpError("Failed to retrieve SNMP metrics from backend.");
    } finally {
      setSnmpLoading(false);
    }
  };

  // Trigger manual SNMP poll
  const handleManualSnmpPoll = async (deviceId) => {
    setSnmpLoading(true);
    setSnmpError(null);
    try {
      const response = await authFetch(`${BACKEND_URL}/api/v1/devices/${deviceId}/snmp/poll`, {
        method: 'POST'
      });
      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || "SNMP poll failed.");
      }
      await fetchSnmpData(deviceId);
      showToast("SNMP device polled successfully!");
    } catch (err) {
      setSnmpError(err.message);
      showToast(err.message, false);
    } finally {
      setSnmpLoading(false);
    }
  };

  // Fetch users when active tab changes to 'users'
  useEffect(() => {
    if (activeTab === 'users' && token && hasAdminRights) {
      fetchUsers();
    }
  }, [activeTab, token]);

  // Initial load and auto refresh timer
  useEffect(() => {
    if (!token) return;
    setLoading(true);
    fetchDevices().finally(() => setLoading(false));

    const timer = setInterval(() => {
      setCountdown(prev => {
        if (prev <= 1) {
          triggerBackgroundRefresh();
          return 10;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [token]);

  const triggerBackgroundRefresh = async () => {
    setIsRefreshing(true);
    await fetchDevices();
    const currentDetailsDevice = detailsDeviceRef.current;
    if (showDetailsModalRef.current && currentDetailsDevice) {
      await fetchDevicePortsStatus(currentDetailsDevice.id);
      if (currentDetailsDevice.snmp_config?.snmp_enabled) {
        await fetchSnmpData(currentDetailsDevice.id);
      }
    }
    setIsRefreshing(false);
  };

  const showToast = (message, isSuccess = true) => {
    if (isSuccess) {
      setSuccessMessage(message);
      setTimeout(() => setSuccessMessage(null), 4000);
    } else {
      setErrorMessage(message);
      setTimeout(() => setErrorMessage(null), 4000);
    }
  };

  // Handle Create Device Submit
  const handleAddSubmit = async (e) => {
    e.preventDefault();
    const parsedPorts = formData.tcp_ports
      ? formData.tcp_ports.split(',').map(p => parseInt(p.trim())).filter(p => !isNaN(p) && p >= 1 && p <= 65535)
      : [];
    const snmpConfig = {
      snmp_enabled: formData.snmp_enabled,
      version: formData.snmp_version,
      community: formData.snmp_community,
      port: parseInt(formData.snmp_port) || 161,
      polling_interval: parseInt(formData.snmp_polling_interval) || 30
    };
    try {
      const response = await authFetch(`${BACKEND_URL}/api/v1/devices/`, {
        method: 'POST',
        body: {
          name: formData.name,
          hostname: formData.hostname,
          ip_address: formData.ip_address,
          device_type: formData.device_type,
          description: formData.description,
          monitoring_enabled: formData.monitoring_enabled,
          ping_interval: parseInt(formData.ping_interval),
          tcp_ports: parsedPorts,
          snmp_config: snmpConfig
        }
      });
      if (!response.ok) {
        const errDetails = await response.json();
        throw new Error(errDetails.detail || "Failed to create device");
      }
      showToast("Device registered and authorized successfully!");
      setShowAddModal(false);
      resetForm();
      fetchDevices();
    } catch (err) {
      showToast(err.message, false);
    }
  };

  // Handle Edit Submit
  const handleEditSubmit = async (e) => {
    e.preventDefault();
    const parsedPorts = formData.tcp_ports
      ? formData.tcp_ports.split(',').map(p => parseInt(p.trim())).filter(p => !isNaN(p) && p >= 1 && p <= 65535)
      : [];
    const snmpConfig = {
      snmp_enabled: formData.snmp_enabled,
      version: formData.snmp_version,
      community: formData.snmp_community,
      port: parseInt(formData.snmp_port) || 161,
      polling_interval: parseInt(formData.snmp_polling_interval) || 30
    };
    try {
      const response = await authFetch(`${BACKEND_URL}/api/v1/devices/${selectedDevice.id}`, {
        method: 'PUT',
        body: {
          name: formData.name,
          hostname: formData.hostname,
          ip_address: formData.ip_address,
          device_type: formData.device_type,
          description: formData.description,
          monitoring_enabled: formData.monitoring_enabled,
          ping_interval: parseInt(formData.ping_interval),
          tcp_ports: parsedPorts,
          snmp_config: snmpConfig
        }
      });
      if (!response.ok) {
        const errDetails = await response.json();
        throw new Error(errDetails.detail || "Failed to update device");
      }
      showToast("Device configurations updated successfully!");
      setShowEditModal(false);
      resetForm();
      fetchDevices();
    } catch (err) {
      showToast(err.message, false);
    }
  };

  // Handle Delete Device
  const handleDeleteDevice = async (id) => {
    if (!window.confirm("Are you sure you want to delete and unauthorize this device? This will erase all diagnostic history.")) return;
    try {
      const response = await authFetch(`${BACKEND_URL}/api/v1/devices/${id}`, {
        method: 'DELETE'
      });
      if (!response.ok) throw new Error("Failed to delete device");
      showToast("Device removed from monitoring.");
      if (detailsDevice && detailsDevice.id === id) {
        setShowDetailsModal(false);
        setDetailsDevice(null);
      }
      fetchDevices();
    } catch (err) {
      showToast(err.message, false);
    }
  };

  // Toggle quick monitoring from list
  const handleToggleMonitoring = async (device) => {
    try {
      const response = await authFetch(`${BACKEND_URL}/api/v1/devices/${device.id}`, {
        method: 'PUT',
        body: {
          monitoring_enabled: !device.monitoring_enabled
        }
      });
      if (!response.ok) throw new Error("Failed to toggle monitoring");
      showToast(`Monitoring ${!device.monitoring_enabled ? 'enabled' : 'disabled'} for ${device.name}`);
      fetchDevices();
    } catch (err) {
      showToast(err.message, false);
    }
  };

  // Trigger manual ping check (POST /monitor)
  const handleManualPing = async (id) => {
    setPingingId(id);
    setManualPingResult(null);
    try {
      const response = await authFetch(`${BACKEND_URL}/api/v1/devices/${id}/monitor`, {
        method: 'POST'
      });
      if (!response.ok) throw new Error("Ping check request failed.");
      const result = await response.json();
      setManualPingResult(result);
      fetchDevices(); // Refresh list to catch updated latency/status
    } catch (err) {
      showToast(err.message, false);
    } finally {
      setPingingId(null);
    }
  };

  const resetForm = () => {
    setFormData({
      name: '',
      hostname: '',
      ip_address: '',
      device_type: 'server',
      description: '',
      monitoring_enabled: true,
      ping_interval: 30,
      tcp_ports: '',
      snmp_enabled: false,
      snmp_version: 'v2c',
      snmp_community: 'public',
      snmp_port: 161,
      snmp_polling_interval: 30
    });
    setSelectedDevice(null);
  };

  const openEditModal = (device) => {
    setSelectedDevice(device);
    const snmpConfig = device.snmp_config || {};
    setFormData({
      name: device.name,
      hostname: device.hostname,
      ip_address: device.ip_address,
      device_type: device.device_type,
      description: device.description || '',
      monitoring_enabled: device.monitoring_enabled,
      ping_interval: device.ping_interval || 30,
      tcp_ports: device.tcp_ports ? device.tcp_ports.join(', ') : '',
      snmp_enabled: snmpConfig.snmp_enabled || false,
      snmp_version: snmpConfig.version || 'v2c',
      snmp_community: snmpConfig.community || 'public',
      snmp_port: snmpConfig.port || 161,
      snmp_polling_interval: snmpConfig.polling_interval || 30
    });
    setShowEditModal(true);
  };

  const openDetailsModal = (device) => {
    setDetailsDevice(device);
    setPortConfigInput(device.tcp_ports ? device.tcp_ports.join(', ') : '');
    setDevicePortsStatus([]);
    setSnmpStatus(null);
    setSnmpSystem(null);
    setSnmpInterfaces([]);
    setSnmpError(null);
    setShowDetailsModal(true);
    fetchDevicePortsStatus(device.id);
    if (device.snmp_config?.snmp_enabled) {
      fetchSnmpData(device.id);
    }
  };

  // Helper mapping for common ports
  const getPortServiceName = (port) => {
    const mapping = {
      21: 'FTP',
      22: 'SSH',
      25: 'SMTP',
      53: 'DNS',
      80: 'HTTP',
      110: 'POP3',
      143: 'IMAP',
      443: 'HTTPS',
      3306: 'MySQL',
      5432: 'PostgreSQL',
      8080: 'HTTP Alternate'
    };
    return mapping[port] || 'Common service';
  };

  // Dynamic statistics calculations
  const totalDevices = devices.length;
  const authorizedMonitored = devices.filter(d => d.monitoring_enabled).length;
  const onlineDevices = devices.filter(d => d.status === 'online');
  const degradedDevices = devices.filter(d => d.status === 'degraded');
  const offlineDevices = devices.filter(d => d.status === 'offline');
  
  // Calculate average latency dynamically from recent logs of online/degraded devices
  const activeDeviceIds = devices.filter(d => d.status !== 'offline').map(d => d.id);
  const activeLogs = recentLogs.filter(log => activeDeviceIds.includes(log.device_id) && log.is_online);
  const avgLatencyVal = activeLogs.length > 0 
    ? (activeLogs.reduce((acc, log) => acc + log.latency_ms, 0) / activeLogs.length).toFixed(1)
    : 0;

  // Calculate overall average packet loss from recent checks
  const avgPacketLossVal = recentLogs.length > 0
    ? (recentLogs.reduce((acc, log) => acc + log.packet_loss_pct, 0) / recentLogs.length).toFixed(1)
    : 0;

  // Alerts: items currently Offline or Degraded
  const activeAlerts = devices.filter(d => d.status === 'offline' || d.status === 'degraded');

  if (!token || !user) {
    return (
      <div className="min-h-screen bg-brand-dark text-slate-100 flex items-center justify-center p-4 font-sans relative overflow-hidden">
        {/* Decorative elements */}
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-brand-primary/10 rounded-full blur-3xl pointer-events-none"></div>
        <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-brand-secondary/10 rounded-full blur-3xl pointer-events-none"></div>
        
        {successMessage && (
          <div className="fixed bottom-5 right-5 z-50 flex items-center gap-2 bg-emerald-500 text-white px-4 py-3 rounded-lg shadow-lg border border-emerald-400/30 animate-bounce">
            <CheckCircle className="h-5 w-5" />
            <span className="text-sm font-medium">{successMessage}</span>
          </div>
        )}
        {errorMessage && (
          <div className="fixed bottom-5 right-5 z-50 flex items-center gap-2 bg-rose-500 text-white px-4 py-3 rounded-lg shadow-lg border border-rose-400/30">
            <AlertTriangle className="h-5 w-5" />
            <span className="text-sm font-medium">{errorMessage}</span>
          </div>
        )}

        <div className="glass-panel w-full max-w-md rounded-2xl p-8 flex flex-col gap-6 shadow-2xl border border-brand-border/80 relative z-10">
          <div className="flex flex-col items-center gap-3 text-center">
            <div className="bg-indigo-600 p-3.5 rounded-2xl text-white shadow-xl shadow-indigo-600/30 flex items-center justify-center">
              <Activity className="h-8 w-8 animate-pulse" />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-white font-display mt-2">NetVision Portal</h1>
              <p className="text-xs text-slate-400 mt-1">Real-time network diagnostic monitoring</p>
            </div>
          </div>

          <form onSubmit={handleLogin} className="flex flex-col gap-4 text-xs mt-2">
            {loginError && (
              <div className="p-3.5 bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs rounded-lg flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 flex-shrink-0" />
                <span>{loginError}</span>
              </div>
            )}

            <div className="flex flex-col gap-1.5">
              <label className="text-slate-400 font-medium">Username or Email</label>
              <input
                type="text"
                required
                placeholder="e.g. admin@netvision.local"
                value={loginUsername}
                onChange={(e) => setLoginUsername(e.target.value)}
                className="bg-slate-950/80 border border-brand-border rounded-xl p-3 text-white focus:outline-none focus:border-brand-primary"
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-slate-400 font-medium">Password</label>
              <input
                type="password"
                required
                placeholder="••••••••"
                value={loginPassword}
                onChange={(e) => setLoginPassword(e.target.value)}
                className="bg-slate-950/80 border border-brand-border rounded-xl p-3 text-white focus:outline-none focus:border-brand-primary"
              />
            </div>

            <button
              type="submit"
              disabled={authLoading}
              className="mt-4 bg-brand-primary hover:bg-indigo-500 disabled:opacity-50 text-white font-medium p-3.5 rounded-xl shadow-lg shadow-brand-primary/20 transition-all flex items-center justify-center gap-2"
            >
              {authLoading ? (
                <>
                  <RefreshCw className="h-4 w-4 animate-spin" />
                  Authenticating...
                </>
              ) : (
                'Secure Log In'
              )}
            </button>
          </form>
        </div>
      </div>
    );
  }

  const navigationTabs = [
    { id: 'overview', label: 'Overview', icon: Activity },
    { id: 'devices', label: 'Devices', icon: Server },
    { id: 'topology', label: 'Topology Map', icon: Layers },
    { id: 'alerts', label: 'Alerts Logs', icon: AlertTriangle }
  ];
  if (hasAdminRights) {
    navigationTabs.push({ id: 'users', label: 'User Accounts', icon: ShieldCheck });
  }

  return (
    <div className="min-h-screen bg-brand-dark text-slate-100 flex flex-col font-sans">
      
      {/* Toast Messages */}
      {successMessage && (
        <div className="fixed bottom-5 right-5 z-50 flex items-center gap-2 bg-emerald-500 text-white px-4 py-3 rounded-lg shadow-lg border border-emerald-400/30 animate-bounce">
          <CheckCircle className="h-5 w-5" />
          <span className="text-sm font-medium">{successMessage}</span>
        </div>
      )}
      {errorMessage && (
        <div className="fixed bottom-5 right-5 z-50 flex items-center gap-2 bg-rose-500 text-white px-4 py-3 rounded-lg shadow-lg border border-rose-400/30">
          <AlertTriangle className="h-5 w-5" />
          <span className="text-sm font-medium">{errorMessage}</span>
        </div>
      )}

      {/* Header Panel */}
      <header className="sticky top-0 z-40 w-full glass-panel border-b border-brand-border px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="bg-indigo-600 p-2 rounded-lg text-white shadow-lg shadow-indigo-600/30 flex items-center justify-center">
            <Activity className="h-6 w-6 animate-pulse" />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight text-white font-display">NetVision</h1>
            <p className="text-xs text-slate-400">Real ICMP & TCP Services poller active</p>
          </div>
        </div>

        <nav className="flex items-center gap-2">
          {navigationTabs.map((tab) => {
            const TabIcon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => {
                  setActiveTab(tab.id);
                  setManualPingResult(null);
                }}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-all flex items-center gap-2 ${
                  activeTab === tab.id 
                    ? 'bg-brand-primary/20 text-brand-primary border border-brand-primary/40' 
                    : 'text-slate-400 hover:text-slate-200 hover:bg-brand-card/50'
                }`}
              >
                <TabIcon className="h-4 w-4" />
                {tab.label}
              </button>
            );
          })}
        </nav>

        <div className="flex items-center gap-4">
          {user && (
            <div className="flex items-center gap-3 border-r border-brand-border/40 pr-4">
              <div className="flex flex-col items-end">
                <span className="text-xs font-semibold text-white">{user.full_name || user.username}</span>
                <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded uppercase tracking-wider ${
                  user.role === 'ADMIN' ? 'bg-purple-500/20 text-purple-400 border border-purple-500/30' :
                  user.role === 'OPERATOR' ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30' :
                  'bg-slate-700/20 text-slate-400 border border-slate-600/30'
                }`}>
                  {user.role}
                </span>
              </div>
            </div>
          )}
          <div className="flex items-center gap-2 text-xs text-slate-400 bg-slate-900/60 px-3 py-1.5 rounded-full border border-brand-border">
            <Clock className={`h-3.5 w-3.5 ${isRefreshing ? 'animate-spin text-brand-primary' : 'text-slate-400'}`} />
            <span>Syncing in {countdown}s</span>
          </div>
          <button 
            onClick={triggerBackgroundRefresh}
            disabled={isRefreshing}
            className="bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs px-3.5 py-2 rounded-lg font-medium border border-brand-border transition-all flex items-center gap-2 disabled:opacity-50"
          >
            <RefreshCw className={`h-3 w-3 ${isRefreshing ? 'animate-spin' : ''}`} />
            Sync
          </button>
          <button 
            onClick={handleLogout}
            className="bg-rose-600 hover:bg-rose-500 text-white text-xs px-3.5 py-2 rounded-lg font-medium shadow-md transition-all flex items-center gap-2"
          >
            Log Out
          </button>
        </div>
      </header>

      {/* Main Core Layout */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-6 flex flex-col gap-6">
        
        {/* Dynamic Metric Cards Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          
          <div className="glass-panel glass-panel-hover rounded-xl p-5 flex flex-col justify-between min-h-[120px]">
            <div className="flex items-center justify-between">
              <span className="text-sm text-slate-400 font-medium">Authorized Devices</span>
              <div className="p-2 rounded-lg bg-slate-800/80 text-brand-primary">
                <Server className="h-5 w-5" />
              </div>
            </div>
            <div className="mt-4">
              <div className="text-2xl font-bold text-white">{totalDevices} Devices</div>
              <div className="text-xs text-slate-400 mt-1">{authorizedMonitored} enabled for polling</div>
            </div>
          </div>

          <div className="glass-panel glass-panel-hover rounded-xl p-5 flex flex-col justify-between min-h-[120px]">
            <div className="flex items-center justify-between">
              <span className="text-sm text-slate-400 font-medium">Average Latency</span>
              <div className="p-2 rounded-lg bg-slate-800/80 text-brand-secondary">
                <Activity className="h-5 w-5" />
              </div>
            </div>
            <div className="mt-4">
              <div className="text-2xl font-bold text-white">
                {avgLatencyVal > 0 ? `${avgLatencyVal} ms` : 'N/A'}
              </div>
              <div className="text-xs text-slate-400 mt-1">Calculated from online hosts</div>
            </div>
          </div>

          <div className="glass-panel glass-panel-hover rounded-xl p-5 flex flex-col justify-between min-h-[120px]">
            <div className="flex items-center justify-between">
              <span className="text-sm text-slate-400 font-medium">Average Packet Loss</span>
              <div className="p-2 rounded-lg bg-slate-800/80 text-amber-500">
                <WifiOff className="h-5 w-5" />
              </div>
            </div>
            <div className="mt-4">
              <div className="text-2xl font-bold text-white">{avgPacketLossVal}%</div>
              <div className="text-xs text-slate-400 mt-1">Combined ICMP target loss</div>
            </div>
          </div>

          <div className="glass-panel glass-panel-hover rounded-xl p-5 flex flex-col justify-between min-h-[120px]">
            <div className="flex items-center justify-between">
              <span className="text-sm text-slate-400 font-medium">Active Warnings</span>
              <div className="p-2 rounded-lg bg-slate-800/80 text-rose-500">
                <AlertTriangle className="h-5 w-5 animate-pulse" />
              </div>
            </div>
            <div className="mt-4">
              <div className="text-2xl font-bold text-white">{alertSummary.total_active} Alerts</div>
              <div className="text-xs text-slate-400 mt-1">
                {alertSummary.critical} critical, {alertSummary.warning} warning
              </div>
            </div>
          </div>

        </div>

        {/* Manual Ping Result Notification Banner */}
        {manualPingResult && (
          <div className={`p-4 rounded-xl border flex flex-col gap-2 relative overflow-hidden ${
            manualPingResult.is_online 
              ? manualPingResult.status === 'degraded'
                ? 'bg-amber-950/40 border-amber-600/30'
                : 'bg-indigo-950/40 border-indigo-600/30'
              : 'bg-rose-950/40 border-rose-600/30'
          }`}>
            <button 
              onClick={() => setManualPingResult(null)}
              className="absolute top-2 right-2 text-slate-400 hover:text-white text-sm px-2 py-0.5 rounded hover:bg-slate-800"
            >
              Close
            </button>
            <div className="flex items-center gap-2">
              <span className="font-semibold text-white">Manual Ping Result Details</span>
              <span className={`px-2 py-0.5 rounded text-2xs uppercase font-semibold ${
                manualPingResult.status === 'online' ? 'bg-emerald-500/20 text-emerald-400' :
                manualPingResult.status === 'degraded' ? 'bg-amber-500/20 text-amber-400' :
                'bg-rose-500/20 text-rose-400'
              }`}>
                {manualPingResult.status}
              </span>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs mt-1 text-slate-300">
              <div>Average Latency: <strong className="text-white">{manualPingResult.latency_ms ? `${manualPingResult.latency_ms.toFixed(2)} ms` : 'N/A'}</strong></div>
              <div>Packet Loss: <strong className="text-white">{manualPingResult.packet_loss_pct}%</strong></div>
              <div>Min/Max Latency: <strong className="text-white">{manualPingResult.min_latency ? `${manualPingResult.min_latency.toFixed(2)} / ${manualPingResult.max_latency.toFixed(2)} ms` : 'N/A'}</strong></div>
              <div>Timestamp: <strong className="text-white">{new Date(manualPingResult.timestamp).toLocaleTimeString()}</strong></div>
            </div>
            {manualPingResult.error_msg && (
              <div className="text-xs text-rose-400 bg-rose-950/30 p-2 rounded mt-2 border border-rose-900/30">
                Error Details: {manualPingResult.error_msg}
              </div>
            )}
          </div>
        )}

        {/* Tab Selection Content Router */}

        {/* 1. OVERVIEW TAB */}
        {activeTab === 'overview' && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            
            {/* Devices Status Overview Table */}
            <div className="lg:col-span-2 flex flex-col gap-6">
              
              <div className="glass-panel rounded-xl p-6 flex flex-col gap-4">
                <div className="flex items-center justify-between border-b border-brand-border pb-4">
                  <div>
                    <h3 className="font-semibold text-white text-base">Network Device Status</h3>
                    <p className="text-xs text-slate-400">Live health of authorized nodes</p>
                  </div>
                  <span className="px-3 py-1 bg-brand-primary/10 border border-brand-primary/30 text-brand-primary rounded-full text-xs font-semibold">
                    Real-time
                  </span>
                </div>

                {loading ? (
                  <div className="py-12 flex flex-col items-center justify-center gap-3">
                    <RefreshCw className="h-8 w-8 text-brand-primary animate-spin" />
                    <span className="text-sm text-slate-400">Polling active network interfaces...</span>
                  </div>
                ) : devices.length === 0 ? (
                  <div className="py-12 flex flex-col items-center justify-center text-center">
                    <Server className="h-12 w-12 text-slate-600 mb-3" />
                    <p className="text-sm text-slate-300 font-semibold">No registered devices found.</p>
                    <p className="text-xs text-slate-500 mt-1">Go to the Devices tab to add and authorize your hardware.</p>
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs border-collapse">
                      <thead>
                        <tr className="border-b border-brand-border/60 text-slate-400 uppercase font-semibold">
                          <th className="py-3 px-2">Device Name</th>
                          <th className="py-3 px-2">IP Address</th>
                          <th className="py-3 px-2">Type</th>
                          <th className="py-3 px-2">Status</th>
                          <th className="py-3 px-2">TCP Services</th>
                          <th className="py-3 px-2 text-right">Actions</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-brand-border/30">
                        {devices.map((device) => (
                          <tr key={device.id} className="hover:bg-slate-800/30 transition-colors">
                            <td className="py-3.5 px-2">
                              <div 
                                className="font-semibold text-slate-200 cursor-pointer hover:text-brand-primary flex items-center gap-1.5"
                                onClick={() => openDetailsModal(device)}
                              >
                                {device.name}
                                <ChevronRight className="h-3.5 w-3.5 text-slate-500" />
                              </div>
                              <div className="text-slate-400 text-3xs">{device.hostname}</div>
                            </td>
                            <td className="py-3.5 px-2 font-mono text-slate-300">{device.ip_address}</td>
                            <td className="py-3.5 px-2 capitalize text-slate-400">{device.device_type}</td>
                            <td className="py-3.5 px-2">
                              <span className={`px-2 py-0.5 rounded text-3xs font-bold uppercase tracking-wider ${
                                device.status === 'online' ? 'bg-emerald-500/20 text-emerald-400' :
                                device.status === 'degraded' ? 'bg-amber-500/20 text-amber-400' :
                                'bg-rose-500/20 text-rose-400'
                              }`}>
                                {device.status}
                              </span>
                            </td>
                            <td className="py-3.5 px-2">
                              {device.tcp_ports && device.tcp_ports.length > 0 ? (
                                <span 
                                  onClick={() => openDetailsModal(device)}
                                  className="text-cyan-400 hover:text-cyan-300 cursor-pointer font-semibold bg-cyan-950/40 border border-cyan-800/30 px-2 py-0.5 rounded text-3xs"
                                >
                                  {device.tcp_ports.length} Monitored
                                </span>
                              ) : (
                                <span className="text-slate-500 text-3xs">None</span>
                              )}
                            </td>
                            <td className="py-3.5 px-2 text-right">
                              <button 
                                onClick={() => handleManualPing(device.id)}
                                disabled={pingingId === device.id}
                                className="bg-slate-800 hover:bg-brand-primary text-slate-200 hover:text-white px-3 py-1.5 rounded-lg text-3xs font-semibold shadow transition-all inline-flex items-center gap-1.5 disabled:opacity-50 animate-pulse-slow"
                              >
                                {pingingId === device.id ? (
                                  <RefreshCw className="h-3 w-3 animate-spin" />
                                ) : (
                                  <Play className="h-3 w-3" />
                                )}
                                Ping
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>

              {/* Recent Metric Logs Table */}
              <div className="glass-panel rounded-xl p-6 flex flex-col gap-4">
                <h3 className="font-semibold text-white text-base border-b border-brand-border pb-4">Recent Network Events & Latency Log</h3>
                {recentLogs.length === 0 ? (
                  <div className="py-8 text-center text-xs text-slate-500">
                    No metric snapshots recorded in database yet. Waiting for background cron cycles...
                  </div>
                ) : (
                  <div className="overflow-x-auto max-h-[300px]">
                    <table className="w-full text-left text-xs border-collapse">
                      <thead>
                        <tr className="border-b border-brand-border/60 text-slate-400 font-semibold uppercase">
                          <th className="py-2.5 px-2">Timestamp</th>
                          <th className="py-2.5 px-2">Target Host</th>
                          <th className="py-2.5 px-2">Avg RTT</th>
                          <th className="py-2.5 px-2">Loss</th>
                          <th className="py-2.5 px-2">State</th>
                          <th className="py-2.5 px-2">Diagnostic Notes</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-brand-border/30">
                        {recentLogs.map((log) => {
                          const dev = devices.find(d => d.id === log.device_id);
                          return (
                            <tr key={log.id} className="hover:bg-slate-800/10 text-slate-300">
                              <td className="py-2.5 px-2 font-mono text-slate-400">{new Date(log.timestamp).toLocaleTimeString()}</td>
                              <td className="py-2.5 px-2 font-medium">{dev ? dev.name : 'Unknown Device'}</td>
                              <td className="py-2.5 px-2 font-mono">{log.latency_ms ? `${log.latency_ms.toFixed(1)} ms` : 'N/A'}</td>
                              <td className="py-2.5 px-2 font-mono">{log.packet_loss_pct}%</td>
                              <td className="py-2.5 px-2 capitalize">
                                <span className={`h-2 w-2 rounded-full inline-block mr-1.5 ${
                                  log.status === 'online' ? 'bg-emerald-500' :
                                  log.status === 'degraded' ? 'bg-amber-500' : 'bg-rose-500'
                                }`}></span>
                                {log.status}
                              </td>
                              <td className="py-2.5 px-2 max-w-[200px] truncate text-slate-400">{log.error_msg || 'Ping sequence complete'}</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>

            </div>

            {/* Right Information Column */}
            <div className="flex flex-col gap-6">
              
              {/* Monitoring Engine Services Health */}
              <div className="glass-panel rounded-xl p-6 flex flex-col gap-4">
                <h3 className="font-semibold text-white text-base border-b border-brand-border pb-3">Services Status</h3>
                <div className="flex flex-col gap-4">
                  <div className="flex items-center justify-between p-3 bg-slate-900/50 rounded-lg border border-slate-800">
                    <div className="flex items-center gap-3">
                      <div className="p-2 bg-indigo-500/10 text-indigo-400 rounded-lg">
                        <Server className="h-4 w-4" />
                      </div>
                      <div>
                        <h4 className="text-xs font-semibold text-slate-200">PostgreSQL DB</h4>
                        <p className="text-2xs text-slate-400 mt-0.5">Port 5432</p>
                      </div>
                    </div>
                    <span className="px-2 py-0.5 bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 rounded text-3xs font-semibold uppercase tracking-wider">
                      online
                    </span>
                  </div>

                  <div className="flex items-center justify-between p-3 bg-slate-900/50 rounded-lg border border-slate-800">
                    <div className="flex items-center gap-3">
                      <div className="p-2 bg-cyan-500/10 text-cyan-400 rounded-lg">
                        <Activity className="h-4 w-4" />
                      </div>
                      <div>
                        <h4 className="text-xs font-semibold text-slate-200">Networking Poller</h4>
                        <p className="text-2xs text-slate-400 mt-0.5">Background Daemon</p>
                      </div>
                    </div>
                    <span className={`px-2 py-0.5 border rounded text-3xs font-semibold uppercase tracking-wider ${
                      totalDevices > 0 
                        ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
                        : 'bg-amber-500/15 text-amber-400 border-amber-500/30'
                    }`}>
                      {totalDevices > 0 ? 'active' : 'idle'}
                    </span>
                  </div>

                  <div className="flex items-center justify-between p-3 bg-slate-900/50 rounded-lg border border-slate-800">
                    <div className="flex items-center gap-3">
                      <div className="p-2 bg-purple-500/10 text-purple-400 rounded-lg">
                        <Terminal className="h-4 w-4" />
                      </div>
                      <div>
                        <h4 className="text-xs font-semibold text-slate-200">FastAPI API Server</h4>
                        <p className="text-2xs text-slate-400 mt-0.5">Port 8000</p>
                      </div>
                    </div>
                    <span className="px-2 py-0.5 bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 rounded text-3xs font-semibold uppercase tracking-wider">
                      online
                    </span>
                  </div>
                </div>
              </div>

              {/* Status Breakdown Panel */}
              <div className="glass-panel rounded-xl p-6 flex flex-col gap-4">
                <h3 className="font-semibold text-white text-base border-b border-brand-border pb-3">Device Status Share</h3>
                <div className="flex flex-col gap-3">
                  <div>
                    <div className="flex justify-between text-xs text-slate-400 mb-1">
                      <span>Online ({onlineDevices.length})</span>
                      <span>{totalDevices > 0 ? ((onlineDevices.length / totalDevices) * 100).toFixed(0) : 0}%</span>
                    </div>
                    <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
                      <div 
                        className="h-full bg-emerald-500 rounded-full transition-all duration-500" 
                        style={{ width: `${totalDevices > 0 ? (onlineDevices.length / totalDevices) * 100 : 0}%` }}
                      ></div>
                    </div>
                  </div>

                  <div>
                    <div className="flex justify-between text-xs text-slate-400 mb-1">
                      <span>Degraded ({degradedDevices.length})</span>
                      <span>{totalDevices > 0 ? ((degradedDevices.length / totalDevices) * 100).toFixed(0) : 0}%</span>
                    </div>
                    <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
                      <div 
                        className="h-full bg-amber-500 rounded-full transition-all duration-500" 
                        style={{ width: `${totalDevices > 0 ? (degradedDevices.length / totalDevices) * 100 : 0}%` }}
                      ></div>
                    </div>
                  </div>

                  <div>
                    <div className="flex justify-between text-xs text-slate-400 mb-1">
                      <span>Offline ({offlineDevices.length})</span>
                      <span>{totalDevices > 0 ? ((offlineDevices.length / totalDevices) * 100).toFixed(0) : 0}%</span>
                    </div>
                    <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
                      <div 
                        className="h-full bg-rose-500 rounded-full transition-all duration-500" 
                        style={{ width: `${totalDevices > 0 ? (offlineDevices.length / totalDevices) * 100 : 0}%` }}
                      ></div>
                    </div>
                  </div>
                </div>
              </div>

            </div>
          </div>
        )}

        {/* 2. DEVICES TAB */}
        {activeTab === 'devices' && (
          <div className="flex flex-col gap-6">
            
            {/* Header control buttons */}
            <div className="flex items-center justify-between border-b border-brand-border pb-4">
              <div>
                <h3 className="font-semibold text-white text-base">Authorized Monitor Targets</h3>
                <p className="text-xs text-slate-400">Add, edit, or configure registered network hardware</p>
              </div>
              {hasAdminRights && (
                <button 
                  onClick={() => {
                    resetForm();
                    setShowAddModal(true);
                  }}
                  className="bg-brand-primary hover:bg-indigo-500 text-white text-xs px-4 py-2.5 rounded-lg font-medium shadow-md transition-all flex items-center gap-2"
                >
                  <Plus className="h-4 w-4" />
                  Register New Device
                </button>
              )}
            </div>

            {/* List Devices */}
            {devices.length === 0 ? (
              <div className="glass-panel rounded-xl p-12 text-center flex flex-col items-center justify-center">
                <HardDrive className="h-12 w-12 text-slate-600 mb-3" />
                <h4 className="text-sm font-semibold text-slate-200">No Network Devices Registered</h4>
                <p className="text-xs text-slate-500 mt-1 max-w-sm">
                  Register server clusters, networking routers, or switches to initiate active ICMP polling processes.
                </p>
                {hasAdminRights && (
                  <button 
                    onClick={() => setShowAddModal(true)}
                    className="mt-4 bg-slate-800 hover:bg-slate-700 text-brand-primary text-xs py-2 px-4 rounded-lg border border-brand-primary/20 transition-all"
                  >
                    Configure first target
                  </button>
                )}
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {devices.map((device) => (
                  <div key={device.id} className="glass-panel glass-panel-hover rounded-xl p-5 flex flex-col justify-between relative border-l-4 border-l-brand-primary">
                    {hasAdminRights && (
                      <div className="absolute top-4 right-4 flex items-center gap-1.5">
                        <button 
                          onClick={() => openEditModal(device)}
                          className="p-1.5 rounded-lg bg-slate-800/80 hover:bg-slate-700 text-slate-300 hover:text-white transition-all"
                          title="Edit configurations"
                        >
                          <Edit3 className="h-3.5 w-3.5" />
                        </button>
                        <button 
                          onClick={() => handleDeleteDevice(device.id)}
                          className="p-1.5 rounded-lg bg-slate-800/80 hover:bg-rose-950/80 text-slate-300 hover:text-rose-400 transition-all border border-transparent hover:border-rose-900/30"
                          title="Delete target"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    )}

                    <div>
                      <div className="flex items-center gap-2">
                        <span className={`h-2.5 w-2.5 rounded-full ${
                          device.status === 'online' ? 'bg-emerald-500' :
                          device.status === 'degraded' ? 'bg-amber-500' :
                          'bg-rose-500'
                        }`}></span>
                        <h4 
                          className="font-semibold text-slate-100 text-sm max-w-[150px] truncate cursor-pointer hover:text-brand-primary"
                          onClick={() => openDetailsModal(device)}
                        >
                          {device.name}
                        </h4>
                      </div>
                      
                      <div className="mt-3 grid grid-cols-2 gap-y-2 gap-x-4 text-xs text-slate-400">
                        <div>IP Address: <span className="font-mono text-slate-200 block">{device.ip_address}</span></div>
                        <div>Hostname: <span className="text-slate-200 block truncate">{device.hostname}</span></div>
                        <div>Type: <span className="text-slate-200 block capitalize">{device.device_type}</span></div>
                        <div>Ping Interval: <span className="text-slate-200 block">{device.ping_interval}s</span></div>
                      </div>

                      {device.description && (
                        <p className="text-2xs text-slate-400 mt-3 bg-slate-900/30 p-2 rounded border border-slate-800/60 line-clamp-2">
                          {device.description}
                        </p>
                      )}
                    </div>

                    <div className="mt-5 border-t border-brand-border/40 pt-4 flex flex-col gap-3">
                      <div className="flex items-center justify-between text-2xs text-slate-400">
                        <span className="flex items-center gap-1">
                          <Clock className="h-3 w-3" />
                          Last: {device.last_seen ? new Date(device.last_seen).toLocaleTimeString() : 'Never'}
                        </span>
                        {device.tcp_ports && device.tcp_ports.length > 0 && (
                          <span className="text-[10px] text-cyan-400 font-semibold bg-cyan-950/40 px-1.5 py-0.5 rounded border border-cyan-900/30">
                            {device.tcp_ports.length} TCP Ports
                          </span>
                        )}
                      </div>
                      
                      <div className="flex gap-2">
                        <button
                          onClick={() => openDetailsModal(device)}
                          className="flex-1 bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white text-3xs py-1.5 px-3 rounded-lg font-semibold transition-all flex items-center justify-center gap-1"
                        >
                          <Settings className="h-3 w-3" />
                          Services
                        </button>
                        
                        {hasOperatorRights && (
                          <button
                            onClick={() => handleManualPing(device.id)}
                            disabled={pingingId === device.id}
                            className="flex-1 bg-brand-primary hover:bg-indigo-500 text-white text-3xs py-1.5 px-3 rounded-lg font-semibold transition-all flex items-center justify-center gap-1 disabled:opacity-50"
                          >
                            {pingingId === device.id ? (
                              <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                            ) : (
                              <Play className="h-3.5 w-3.5" />
                            )}
                            Ping Now
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}

          </div>
        )}

        {/* 3. TOPOLOGY TAB */}
        {activeTab === 'topology' && (
          <div className="glass-panel rounded-xl p-6 flex flex-col gap-4 min-h-[450px]">
            <div className="flex items-center justify-between border-b border-brand-border pb-4">
              <div>
                <h3 className="font-semibold text-white text-base">Interactive Network Topology Map</h3>
                <p className="text-xs text-slate-400">Live coordinates representing link health between poller node and authorized hosts</p>
              </div>
              <span className="px-3 py-1 bg-cyan-950 text-cyan-400 border border-cyan-800/30 rounded-full text-xs font-semibold">
                SVG Canvas Rendering
              </span>
            </div>

            {devices.length === 0 ? (
              <div className="flex-1 flex flex-col items-center justify-center border border-dashed border-slate-700/50 rounded-lg p-6 bg-slate-900/30 text-center">
                <Layers className="h-10 w-10 text-slate-600 mb-2" />
                <h4 className="text-sm font-semibold text-slate-300">Topology Canvas Empty</h4>
                <p className="text-xs text-slate-500 mt-1 max-w-xs">Register at least one networking device to view active connections.</p>
              </div>
            ) : (
              <div className="flex-1 border border-slate-800 rounded-lg bg-slate-950/60 overflow-hidden relative min-h-[350px] flex items-center justify-center">
                
                {/* Dynamic SVG link connections */}
                <svg className="absolute inset-0 w-full h-full pointer-events-none">
                  {devices.map((device, idx) => {
                    const cx = 350; // SVG Width center representation
                    const cy = 200; // SVG Height center representation
                    const radius = 130;
                    const angle = (idx * 2 * Math.PI) / devices.length;
                    const x = cx + radius * Math.cos(angle);
                    const y = cy + radius * Math.sin(angle);
                    
                    const isOnline = device.status === 'online';
                    const isDegraded = device.status === 'degraded';
                    
                    return (
                      <g key={`link-${device.id}`}>
                        <line 
                          x1={cx} 
                          y1={cy} 
                          x2={x} 
                          y2={y} 
                          className={`stroke-2 ${
                            isOnline ? 'stroke-emerald-600/40' :
                            isDegraded ? 'stroke-amber-600/40' :
                            'stroke-rose-600/40'
                          }`}
                        />
                        {/* Animated pulses along lines */}
                        {(isOnline || isDegraded) && (
                          <circle r="4" fill={isOnline ? "#10B981" : "#F59E0B"}>
                            <animateMotion 
                              path={`M ${cx} ${cy} L ${x} ${y}`} 
                              dur="3s" 
                              repeatCount="indefinite" 
                            />
                          </circle>
                        )}
                      </g>
                    );
                  })}
                </svg>

                {/* DOM Nodes aligned above SVG */}
                <div className="relative w-full h-[400px]">
                  
                  {/* Central Node representing NetVision Dashboard */}
                  <div className="absolute top-[200px] left-[350px] transform -translate-x-1/2 -translate-y-1/2 z-10 flex flex-col items-center">
                    <div className="w-14 h-14 rounded-full bg-brand-dark border-2 border-brand-primary shadow-lg shadow-indigo-600/20 flex items-center justify-center text-brand-primary">
                      <Activity className="h-6 w-6 animate-pulse" />
                    </div>
                    <span className="text-2xs font-semibold text-white bg-indigo-950/80 px-2 py-0.5 rounded border border-indigo-500/30 mt-2 whitespace-nowrap">
                      NetVision Poller
                    </span>
                  </div>

                  {/* Outer Nodes for Devices */}
                  {devices.map((device, idx) => {
                    const cx = 350;
                    const cy = 200;
                    const radius = 130;
                    const angle = (idx * 2 * Math.PI) / devices.length;
                    const x = cx + radius * Math.cos(angle);
                    const y = cy + radius * Math.sin(angle);
                    
                    return (
                      <div 
                        key={device.id}
                        className="absolute transform -translate-x-1/2 -translate-y-1/2 z-10 flex flex-col items-center cursor-pointer group"
                        style={{ left: `${x}px`, top: `${y}px` }}
                        onClick={() => openDetailsModal(device)}
                      >
                        <div className={`w-10 h-10 rounded-full bg-brand-dark border-2 flex items-center justify-center transition-all group-hover:scale-110 shadow-md ${
                          device.status === 'online' ? 'border-emerald-500 text-emerald-400 shadow-emerald-500/10' :
                          device.status === 'degraded' ? 'border-amber-500 text-amber-400 shadow-amber-500/10' :
                          'border-rose-500 text-rose-400 shadow-rose-500/10'
                        }`}>
                          <Server className="h-4.5 w-4.5" />
                        </div>
                        <div className="mt-2 bg-slate-900/90 border border-brand-border px-2 py-0.5 rounded text-4xs font-semibold text-slate-200 whitespace-nowrap text-center max-w-[90px] truncate shadow">
                          {device.name}
                          <span className="block text-slate-400 text-[8px] font-mono">{device.ip_address}</span>
                        </div>
                      </div>
                    );
                  })}

                </div>

              </div>
            )}
          </div>
        )}

        {/* 4. ALERTS LOG TAB */}
        {activeTab === 'alerts' && (
          <div className="flex flex-col gap-6">
            
            {/* Summary Statistics Mini Bar */}
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
              <div className="glass-panel p-4 rounded-xl flex flex-col gap-1">
                <span className="text-2xs text-slate-400 font-semibold uppercase">Active Incidents</span>
                <span className="text-xl font-bold text-white">{alertSummary.total_active}</span>
              </div>
              <div className="glass-panel p-4 rounded-xl flex flex-col gap-1">
                <span className="text-2xs text-rose-400 font-semibold uppercase">Critical Active</span>
                <span className="text-xl font-bold text-rose-500">{alertSummary.critical}</span>
              </div>
              <div className="glass-panel p-4 rounded-xl flex flex-col gap-1">
                <span className="text-2xs text-amber-400 font-semibold uppercase">Warning Active</span>
                <span className="text-xl font-bold text-amber-500">{alertSummary.warning}</span>
              </div>
              <div className="glass-panel p-4 rounded-xl flex flex-col gap-1">
                <span className="text-2xs text-blue-400 font-semibold uppercase">Acknowledged</span>
                <span className="text-xl font-bold text-blue-500">{alertSummary.acknowledged}</span>
              </div>
              <div className="glass-panel p-4 rounded-xl flex flex-col gap-1">
                <span className="text-2xs text-emerald-400 font-semibold uppercase">Resolved History</span>
                <span className="text-xl font-bold text-emerald-500">{alertSummary.resolved}</span>
              </div>
            </div>

            {/* Threshold Settings Panel (Expandable) */}
            {showSettingsPanel && (
              <form onSubmit={handleSaveAlertSettings} className="glass-panel p-6 rounded-xl border border-brand-primary/30 flex flex-col gap-4 animate-in slide-in-from-top-4 duration-200">
                <div className="flex items-center justify-between border-b border-brand-border pb-3">
                  <div>
                    <h4 className="font-semibold text-white text-sm">Alert Rules & Thresholds</h4>
                    <p className="text-2xs text-slate-400">Configure global limits for automated anomaly detection</p>
                  </div>
                  <button 
                    type="button" 
                    onClick={() => setShowSettingsPanel(false)}
                    className="text-slate-400 hover:text-white text-xs"
                  >
                    ✕ Close
                  </button>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
                  <div className="flex flex-col gap-1.5">
                    <label className="text-slate-400 font-medium">ICMP Latency Warning (ms)</label>
                    <input 
                      type="number" 
                      required
                      value={alertSettings.icmp_latency_warning}
                      onChange={(e) => setAlertSettings({...alertSettings, icmp_latency_warning: parseFloat(e.target.value) || 0})}
                      className="bg-slate-900 border border-brand-border rounded-lg p-2 text-white focus:outline-none focus:border-brand-primary"
                    />
                  </div>
                  <div className="flex flex-col gap-1.5">
                    <label className="text-slate-400 font-medium">ICMP Latency Critical (ms)</label>
                    <input 
                      type="number" 
                      required
                      value={alertSettings.icmp_latency_critical}
                      onChange={(e) => setAlertSettings({...alertSettings, icmp_latency_critical: parseFloat(e.target.value) || 0})}
                      className="bg-slate-900 border border-brand-border rounded-lg p-2 text-white focus:outline-none focus:border-brand-primary"
                    />
                  </div>
                  <div className="flex flex-col gap-1.5">
                    <label className="text-slate-400 font-medium">Packet Loss Warning (%)</label>
                    <input 
                      type="number" 
                      required
                      min="0"
                      max="100"
                      value={alertSettings.packet_loss_warning}
                      onChange={(e) => setAlertSettings({...alertSettings, packet_loss_warning: parseFloat(e.target.value) || 0})}
                      className="bg-slate-900 border border-brand-border rounded-lg p-2 text-white focus:outline-none focus:border-brand-primary"
                    />
                  </div>
                  <div className="flex flex-col gap-1.5">
                    <label className="text-slate-400 font-medium">Packet Loss Critical (%)</label>
                    <input 
                      type="number" 
                      required
                      min="0"
                      max="100"
                      value={alertSettings.packet_loss_critical}
                      onChange={(e) => setAlertSettings({...alertSettings, packet_loss_critical: parseFloat(e.target.value) || 0})}
                      className="bg-slate-900 border border-brand-border rounded-lg p-2 text-white focus:outline-none focus:border-brand-primary"
                    />
                  </div>
                  <div className="flex flex-col gap-1.5">
                    <label className="text-slate-400 font-medium">SNMP Traffic Warning (Mbps)</label>
                    <input 
                      type="number" 
                      required
                      value={alertSettings.snmp_traffic_warning_bps / 1000000}
                      onChange={(e) => setAlertSettings({...alertSettings, snmp_traffic_warning_bps: (parseFloat(e.target.value) || 0) * 1000000})}
                      className="bg-slate-900 border border-brand-border rounded-lg p-2 text-white focus:outline-none focus:border-brand-primary"
                    />
                  </div>
                </div>

                <div className="flex items-center gap-3 justify-end mt-2">
                  <button 
                    type="button"
                    onClick={() => setShowSettingsPanel(false)}
                    className="bg-slate-900 hover:bg-slate-800 text-white text-xs px-4 py-2 rounded-lg border border-brand-border font-medium"
                  >
                    Cancel
                  </button>
                  <button 
                    type="submit"
                    disabled={isSavingSettings}
                    className="bg-brand-primary hover:bg-indigo-500 text-white text-xs px-4 py-2 rounded-lg font-medium shadow-md"
                  >
                    {isSavingSettings ? 'Saving...' : 'Save Settings'}
                  </button>
                </div>
              </form>
            )}

            {/* Filter controls */}
            <div className="glass-panel p-4 rounded-xl flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div className="flex flex-wrap items-center gap-2">
                {[
                  { id: 'ACTIVE', label: 'Active Incidents' },
                  { id: 'OPEN', label: 'Open' },
                  { id: 'ACKNOWLEDGED', label: 'Acknowledged' },
                  { id: 'RESOLVED', label: 'Resolved History' },
                  { id: 'ALL', label: 'All Alerts' }
                ].map(filter => (
                  <button
                    key={filter.id}
                    onClick={() => setAlertFilters({...alertFilters, status: filter.id})}
                    className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                      alertFilters.status === filter.id 
                        ? 'bg-brand-primary/20 text-brand-primary border border-brand-primary/30' 
                        : 'text-slate-400 hover:text-slate-200 bg-slate-900/60 border border-transparent'
                    }`}
                  >
                    {filter.label}
                  </button>
                ))}
              </div>

              <div className="flex items-center gap-3">
                <div className="flex items-center gap-2 text-xs">
                  <span className="text-slate-400 font-medium">Severity:</span>
                  <select 
                    value={alertFilters.severity}
                    onChange={(e) => setAlertFilters({...alertFilters, severity: e.target.value})}
                    className="bg-slate-900 border border-brand-border rounded-lg px-2.5 py-1.5 text-white focus:outline-none focus:border-brand-primary"
                  >
                    <option value="ALL">All Severities</option>
                    <option value="CRITICAL">Critical</option>
                    <option value="WARNING">Warning</option>
                    <option value="INFO">Info</option>
                  </select>
                </div>

                <button 
                  onClick={() => setShowSettingsPanel(!showSettingsPanel)}
                  className={`p-2 rounded-lg border text-xs font-medium transition-all flex items-center gap-1.5 ${
                    showSettingsPanel
                      ? 'bg-brand-primary text-white border-brand-primary'
                      : 'bg-slate-900/60 hover:bg-slate-800 text-slate-300 border-brand-border'
                  }`}
                >
                  <Settings className="h-4 w-4" />
                  Rules
                </button>
              </div>
            </div>

            {/* List of alerts */}
            <div className="flex flex-col gap-4">
              {alerts.filter(alert => {
                // Status Filter
                if (alertFilters.status === 'ACTIVE' && alert.status === 'RESOLVED') return false;
                if (alertFilters.status !== 'ACTIVE' && alertFilters.status !== 'ALL' && alert.status !== alertFilters.status) return false;
                // Severity Filter
                if (alertFilters.severity !== 'ALL' && alert.severity !== alertFilters.severity) return false;
                return true;
              }).length === 0 ? (
                <div className="glass-panel py-16 flex flex-col items-center justify-center text-center">
                  <CheckCircle className="h-12 w-12 text-emerald-500 mb-2 animate-bounce" />
                  <h4 className="text-sm font-semibold text-slate-200">No matching alerts found</h4>
                  <p className="text-xs text-slate-500 mt-1">Everything matches your filters and is working correctly.</p>
                </div>
              ) : (
                alerts.filter(alert => {
                  if (alertFilters.status === 'ACTIVE' && alert.status === 'RESOLVED') return false;
                  if (alertFilters.status !== 'ACTIVE' && alertFilters.status !== 'ALL' && alert.status !== alertFilters.status) return false;
                  if (alertFilters.severity !== 'ALL' && alert.severity !== alertFilters.severity) return false;
                  return true;
                }).map(alert => {
                  const deviceName = alert.device ? (alert.device.name || alert.device.hostname) : 'Unknown Device';
                  const deviceHost = alert.device ? alert.device.hostname : 'unknown';
                  const isResolved = alert.status === 'RESOLVED';
                  const isAck = alert.status === 'ACKNOWLEDGED';
                  
                  let cardStyles = 'bg-slate-950/20 border-slate-500/20 text-slate-300';
                  let iconStyles = 'text-slate-400';
                  
                  if (!isResolved) {
                    if (alert.severity === 'CRITICAL') {
                      cardStyles = 'bg-rose-950/20 border-rose-500/30 text-rose-300';
                      iconStyles = 'text-rose-500';
                    } else if (alert.severity === 'WARNING') {
                      cardStyles = 'bg-amber-950/20 border-amber-500/30 text-amber-300';
                      iconStyles = 'text-amber-500';
                    } else {
                      cardStyles = 'bg-blue-950/20 border-blue-500/30 text-blue-300';
                      iconStyles = 'text-blue-500';
                    }
                  } else {
                    cardStyles = 'bg-emerald-950/10 border-emerald-500/20 text-emerald-300/80';
                    iconStyles = 'text-emerald-500';
                  }

                  return (
                    <div 
                      key={alert.id} 
                      className={`p-5 rounded-xl border flex flex-col md:flex-row md:items-center justify-between gap-4 transition-all hover:bg-slate-900/40 ${cardStyles}`}
                    >
                      <div className="flex items-start gap-4">
                        <AlertTriangle className={`h-5 w-5 mt-0.5 flex-shrink-0 ${!isResolved ? 'animate-pulse' : ''} ${iconStyles}`} />
                        <div className="flex flex-col gap-1">
                          <div className="flex items-center gap-2 flex-wrap">
                            <h4 className="text-sm font-semibold text-white">{alert.title}</h4>
                            <span className={`px-2 py-0.5 rounded text-3xs font-semibold uppercase ${
                              alert.severity === 'CRITICAL' ? 'bg-rose-500/20 text-rose-400' :
                              alert.severity === 'WARNING' ? 'bg-amber-500/20 text-amber-400' :
                              'bg-blue-500/20 text-blue-400'
                            }`}>
                              {alert.severity}
                            </span>
                            <span className={`px-2 py-0.5 rounded text-3xs font-semibold uppercase ${
                              isResolved ? 'bg-emerald-500/20 text-emerald-400' :
                              isAck ? 'bg-blue-500/20 text-blue-400' :
                              'bg-rose-500/20 text-rose-400 animate-pulse'
                            }`}>
                              {alert.status}
                            </span>
                          </div>
                          
                          <p className="text-xs text-slate-300 mt-0.5">{alert.message}</p>
                          
                          <div className="flex flex-wrap gap-4 text-3xs text-slate-400 mt-1.5">
                            <div>Device: <strong className="text-slate-200">{deviceName} ({deviceHost})</strong></div>
                            {alert.monitored_resource && (
                              <div>Resource: <strong className="text-slate-200">{alert.monitored_resource}</strong></div>
                            )}
                            {alert.current_value && (
                              <div>Value: <strong className="text-slate-200">{alert.current_value}</strong> <span className="text-slate-500">(Threshold: {alert.threshold})</span></div>
                            )}
                          </div>

                          <div className="flex flex-wrap gap-x-4 gap-y-1 text-3xs text-slate-500 mt-1 font-mono">
                            <div>Triggered: {new Date(alert.created_at).toLocaleString()}</div>
                            {alert.acknowledged_at && (
                              <div>Acked: {new Date(alert.acknowledged_at).toLocaleString()}</div>
                            )}
                            {alert.resolved_at && (
                              <div>Resolved: {new Date(alert.resolved_at).toLocaleString()}</div>
                            )}
                          </div>
                        </div>
                      </div>

                      {!isResolved && (
                        <div className="flex items-center gap-2 self-end md:self-center">
                          {!isAck && (
                            <button
                              onClick={() => handleAcknowledgeAlert(alert.id)}
                              className="bg-slate-900 hover:bg-slate-800 text-white text-xs px-3 py-1.5 rounded-lg border border-brand-border transition-all flex items-center gap-1 font-medium"
                            >
                              <Clock className="h-3.5 w-3.5" />
                              Ack
                            </button>
                          )}
                          <button
                            onClick={() => handleResolveAlert(alert.id)}
                            className="bg-emerald-600 hover:bg-emerald-500 text-white text-xs px-3 py-1.5 rounded-lg font-medium shadow-md transition-all flex items-center gap-1"
                          >
                            <CheckCircle className="h-3.5 w-3.5" />
                            Resolve
                          </button>
                        </div>
                      )}
                    </div>
                  );
                })
              )}
            </div>
          </div>
        )}

        {/* 5. USER ACCOUNTS TAB */}
        {activeTab === 'users' && hasAdminRights && (
          <div className="flex flex-col gap-6">
            
            {/* Header control buttons */}
            <div className="flex items-center justify-between border-b border-brand-border pb-4">
              <div>
                <h3 className="font-semibold text-white text-base">User Accounts</h3>
                <p className="text-xs text-slate-400">Manage portal operators, viewers, and administrators</p>
              </div>
              <button 
                onClick={() => {
                  resetUserForm();
                  setShowAddUserModal(true);
                }}
                className="bg-brand-primary hover:bg-indigo-500 text-white text-xs px-4 py-2.5 rounded-lg font-medium shadow-md transition-all flex items-center gap-2"
              >
                <UserPlus className="h-4 w-4" />
                Register New User
              </button>
            </div>

            {/* List Users */}
            {usersLoading && usersList.length === 0 ? (
              <div className="py-12 flex flex-col items-center justify-center gap-2">
                <RefreshCw className="h-6 w-6 text-brand-primary animate-spin" />
                <span className="text-xs text-slate-400">Loading user accounts...</span>
              </div>
            ) : (
              <div className="glass-panel rounded-xl p-6 flex flex-col gap-4">
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs border-collapse">
                    <thead>
                      <tr className="border-b border-brand-border/60 text-slate-400 font-semibold uppercase">
                        <th className="py-3 px-3">Full Name</th>
                        <th className="py-3 px-3">Username</th>
                        <th className="py-3 px-3">Email Address</th>
                        <th className="py-3 px-3">System Role</th>
                        <th className="py-3 px-3">Status</th>
                        <th className="py-3 px-3 text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-brand-border/30">
                      {usersList.map((targetUser) => (
                        <tr key={targetUser.id} className="hover:bg-slate-800/30 transition-colors text-slate-300">
                          <td className="py-3 px-3 font-semibold text-white">{targetUser.full_name || '—'}</td>
                          <td className="py-3 px-3 font-mono">{targetUser.username || '—'}</td>
                          <td className="py-3 px-3">{targetUser.email}</td>
                          <td className="py-3 px-3">
                            <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
                              targetUser.role === 'ADMIN' ? 'bg-purple-500/20 text-purple-400 border border-purple-500/30' :
                              targetUser.role === 'OPERATOR' ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30' :
                              'bg-slate-700/20 text-slate-400 border border-slate-600/30'
                            }`}>
                              {targetUser.role}
                            </span>
                          </td>
                          <td className="py-3 px-3">
                            <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
                              targetUser.is_active ? 'bg-emerald-500/20 text-emerald-400' : 'bg-rose-500/20 text-rose-400'
                            }`}>
                              {targetUser.is_active ? 'Active' : 'Inactive'}
                            </span>
                          </td>
                          <td className="py-3 px-3 text-right">
                            <div className="flex items-center justify-end gap-1.5">
                              <button 
                                onClick={() => openEditUserModal(targetUser)}
                                className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition-all"
                                title="Edit user settings"
                              >
                                <Edit3 className="h-3.5 w-3.5" />
                              </button>
                              <button 
                                onClick={() => handleDeleteUser(targetUser)}
                                disabled={targetUser.id === user?.id}
                                className="p-1.5 rounded-lg bg-slate-800 hover:bg-rose-950 text-slate-300 hover:text-rose-400 disabled:opacity-30 disabled:pointer-events-none transition-all border border-transparent hover:border-rose-900/30"
                                title="Delete user"
                              >
                                <Trash2 className="h-3.5 w-3.5" />
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}

      </main>

      {/* CREATE DEVICE MODAL */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="glass-panel w-full max-w-md rounded-xl p-6 flex flex-col gap-4 animate-in fade-in-50 zoom-in-95">
            <div className="flex items-center justify-between border-b border-brand-border pb-3">
              <h3 className="text-base font-semibold text-white">Register Target for Polling</h3>
              <button onClick={() => setShowAddModal(false)} className="text-slate-400 hover:text-white">✕</button>
            </div>
            
            <form onSubmit={handleAddSubmit} className="flex flex-col gap-4 text-xs">
              <div className="flex flex-col gap-1.5">
                <label className="text-slate-400 font-medium">Device Name</label>
                <input 
                  type="text" 
                  required
                  placeholder="e.g. Gateway Router" 
                  value={formData.name}
                  onChange={(e) => setFormData({...formData, name: e.target.value})}
                  className="bg-slate-900 border border-brand-border rounded-lg p-2.5 text-white focus:outline-none focus:border-brand-primary"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="flex flex-col gap-1.5">
                  <label className="text-slate-400 font-medium">Hostname</label>
                  <input 
                    type="text" 
                    placeholder="e.g. gateway.local" 
                    value={formData.hostname}
                    onChange={(e) => setFormData({...formData, hostname: e.target.value})}
                    className="bg-slate-900 border border-brand-border rounded-lg p-2.5 text-white focus:outline-none focus:border-brand-primary"
                  />
                </div>
                <div className="flex flex-col gap-1.5">
                  <label className="text-slate-400 font-medium">IPv4 Address</label>
                  <input 
                    type="text" 
                    required
                    placeholder="e.g. 192.168.1.1" 
                    value={formData.ip_address}
                    onChange={(e) => setFormData({...formData, ip_address: e.target.value})}
                    className="bg-slate-900 border border-brand-border rounded-lg p-2.5 text-white focus:outline-none focus:border-brand-primary font-mono"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="flex flex-col gap-1.5">
                  <label className="text-slate-400 font-medium">Device Type</label>
                  <select 
                    value={formData.device_type}
                    onChange={(e) => setFormData({...formData, device_type: e.target.value})}
                    className="bg-slate-900 border border-brand-border rounded-lg p-2.5 text-white focus:outline-none focus:border-brand-primary"
                  >
                    <option value="router">Router</option>
                    <option value="switch">Switch</option>
                    <option value="firewall">Firewall</option>
                    <option value="server">Server</option>
                    <option value="workstation">Workstation</option>
                    <option value="other">Other</option>
                  </select>
                </div>
                <div className="flex flex-col gap-1.5">
                  <label className="text-slate-400 font-medium">Interval (seconds)</label>
                  <input 
                    type="number" 
                    min="5"
                    max="3600"
                    value={formData.ping_interval}
                    onChange={(e) => setFormData({...formData, ping_interval: e.target.value})}
                    className="bg-slate-900 border border-brand-border rounded-lg p-2.5 text-white focus:outline-none focus:border-brand-primary"
                  />
                </div>
              </div>

              <div className="flex flex-col gap-1.5">
                <label className="text-slate-400 font-medium">Monitored TCP Ports</label>
                <input 
                  type="text" 
                  placeholder="e.g. 22, 80, 443 (comma separated)" 
                  value={formData.tcp_ports}
                  onChange={(e) => setFormData({...formData, tcp_ports: e.target.value})}
                  className="bg-slate-900 border border-brand-border rounded-lg p-2.5 text-white focus:outline-none focus:border-brand-primary font-mono"
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <label className="text-slate-400 font-medium">Description</label>
                <textarea 
                  placeholder="Additional node attributes..." 
                  value={formData.description}
                  onChange={(e) => setFormData({...formData, description: e.target.value})}
                  className="bg-slate-900 border border-brand-border rounded-lg p-2.5 text-white focus:outline-none focus:border-brand-primary min-h-[60px]"
                />
              </div>

              <div className="flex items-center gap-2 mt-2">
                <input 
                  type="checkbox" 
                  id="monitoring_enabled"
                  checked={formData.monitoring_enabled}
                  onChange={(e) => setFormData({...formData, monitoring_enabled: e.target.checked})}
                  className="rounded border-brand-border bg-slate-900 text-brand-primary focus:ring-0"
                />
                <label htmlFor="monitoring_enabled" className="text-slate-300 font-medium cursor-pointer">Enable active background ICMP monitoring</label>
              </div>

              {/* SNMP Configuration Accordion */}
              <div className="border-t border-brand-border/40 pt-4 mt-2">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-semibold text-slate-300">SNMP Configuration</span>
                  <div className="flex items-center gap-1.5">
                    <input 
                      type="checkbox" 
                      id="snmp_enabled"
                      checked={formData.snmp_enabled}
                      onChange={(e) => setFormData({...formData, snmp_enabled: e.target.checked})}
                      className="rounded border-brand-border bg-slate-900 text-brand-primary focus:ring-0"
                    />
                    <label htmlFor="snmp_enabled" className="text-slate-400 font-medium cursor-pointer">Enable SNMP</label>
                  </div>
                </div>

                {formData.snmp_enabled && (
                  <div className="grid grid-cols-2 gap-3 mt-3 p-3 bg-slate-900/60 rounded-lg border border-brand-border/40 animate-in fade-in-50 duration-200">
                    <div className="flex flex-col gap-1">
                      <label className="text-slate-400 text-2xs font-medium">Version</label>
                      <select 
                        value={formData.snmp_version}
                        onChange={(e) => setFormData({...formData, snmp_version: e.target.value})}
                        className="bg-slate-900 border border-brand-border rounded p-1.5 text-white focus:outline-none text-2xs"
                      >
                        <option value="v2c">v2c</option>
                        <option value="v3">v3 (Coming Soon)</option>
                      </select>
                    </div>
                    <div className="flex flex-col gap-1">
                      <label className="text-slate-400 text-2xs font-medium">Community String</label>
                      <input 
                        type="text" 
                        placeholder="public"
                        value={formData.snmp_community}
                        onChange={(e) => setFormData({...formData, snmp_community: e.target.value})}
                        className="bg-slate-900 border border-brand-border rounded p-1.5 text-white focus:outline-none text-2xs"
                      />
                    </div>
                    <div className="flex flex-col gap-1">
                      <label className="text-slate-400 text-2xs font-medium">Port</label>
                      <input 
                        type="number" 
                        min="1"
                        max="65535"
                        value={formData.snmp_port}
                        onChange={(e) => setFormData({...formData, snmp_port: e.target.value})}
                        className="bg-slate-900 border border-brand-border rounded p-1.5 text-white focus:outline-none text-2xs font-mono"
                      />
                    </div>
                    <div className="flex flex-col gap-1">
                      <label className="text-slate-400 text-2xs font-medium">Poll Interval (s)</label>
                      <input 
                        type="number" 
                        min="5"
                        max="3600"
                        value={formData.snmp_polling_interval}
                        onChange={(e) => setFormData({...formData, snmp_polling_interval: e.target.value})}
                        className="bg-slate-900 border border-brand-border rounded p-1.5 text-white focus:outline-none text-2xs font-mono"
                      />
                    </div>
                  </div>
                )}
              </div>

              <button 
                type="submit" 
                className="mt-4 bg-brand-primary hover:bg-indigo-500 text-white font-medium p-2.5 rounded-lg shadow-md transition-all text-xs"
              >
                Register Target
              </button>
            </form>
          </div>
        </div>
      )}

      {/* EDIT DEVICE MODAL */}
      {showEditModal && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="glass-panel w-full max-w-md rounded-xl p-6 flex flex-col gap-4 animate-in fade-in-50 zoom-in-95">
            <div className="flex items-center justify-between border-b border-brand-border pb-3">
              <h3 className="text-base font-semibold text-white">Modify Device Configurations</h3>
              <button 
                onClick={() => {
                  setShowEditModal(false);
                  resetForm();
                }} 
                className="text-slate-400 hover:text-white"
              >
                ✕
              </button>
            </div>
            
            <form onSubmit={handleEditSubmit} className="flex flex-col gap-4 text-xs">
              <div className="flex flex-col gap-1.5">
                <label className="text-slate-400 font-medium">Device Name</label>
                <input 
                  type="text" 
                  required
                  placeholder="e.g. Gateway Router" 
                  value={formData.name}
                  onChange={(e) => setFormData({...formData, name: e.target.value})}
                  className="bg-slate-900 border border-brand-border rounded-lg p-2.5 text-white focus:outline-none focus:border-brand-primary"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="flex flex-col gap-1.5">
                  <label className="text-slate-400 font-medium">Hostname</label>
                  <input 
                    type="text" 
                    placeholder="e.g. gateway.local" 
                    value={formData.hostname}
                    onChange={(e) => setFormData({...formData, hostname: e.target.value})}
                    className="bg-slate-900 border border-brand-border rounded-lg p-2.5 text-white focus:outline-none focus:border-brand-primary"
                  />
                </div>
                <div className="flex flex-col gap-1.5">
                  <label className="text-slate-400 font-medium">IPv4 Address</label>
                  <input 
                    type="text" 
                    required
                    placeholder="e.g. 192.168.1.1" 
                    value={formData.ip_address}
                    onChange={(e) => setFormData({...formData, ip_address: e.target.value})}
                    className="bg-slate-900 border border-brand-border rounded-lg p-2.5 text-white focus:outline-none focus:border-brand-primary font-mono"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="flex flex-col gap-1.5">
                  <label className="text-slate-400 font-medium">Device Type</label>
                  <select 
                    value={formData.device_type}
                    onChange={(e) => setFormData({...formData, device_type: e.target.value})}
                    className="bg-slate-900 border border-brand-border rounded-lg p-2.5 text-white focus:outline-none focus:border-brand-primary"
                  >
                    <option value="router">Router</option>
                    <option value="switch">Switch</option>
                    <option value="firewall">Firewall</option>
                    <option value="server">Server</option>
                    <option value="workstation">Workstation</option>
                    <option value="other">Other</option>
                  </select>
                </div>
                <div className="flex flex-col gap-1.5">
                  <label className="text-slate-400 font-medium">Interval (seconds)</label>
                  <input 
                    type="number" 
                    min="5"
                    max="3600"
                    value={formData.ping_interval}
                    onChange={(e) => setFormData({...formData, ping_interval: e.target.value})}
                    className="bg-slate-900 border border-brand-border rounded-lg p-2.5 text-white focus:outline-none focus:border-brand-primary"
                  />
                </div>
              </div>

              <div className="flex flex-col gap-1.5">
                <label className="text-slate-400 font-medium">Monitored TCP Ports</label>
                <input 
                  type="text" 
                  placeholder="e.g. 22, 80, 443 (comma separated)" 
                  value={formData.tcp_ports}
                  onChange={(e) => setFormData({...formData, tcp_ports: e.target.value})}
                  className="bg-slate-900 border border-brand-border rounded-lg p-2.5 text-white focus:outline-none focus:border-brand-primary font-mono"
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <label className="text-slate-400 font-medium">Description</label>
                <textarea 
                  placeholder="Additional node attributes..." 
                  value={formData.description}
                  onChange={(e) => setFormData({...formData, description: e.target.value})}
                  className="bg-slate-900 border border-brand-border rounded-lg p-2.5 text-white focus:outline-none focus:border-brand-primary min-h-[60px]"
                />
              </div>

              <div className="flex items-center gap-2 mt-2">
                <input 
                  type="checkbox" 
                  id="edit_monitoring_enabled"
                  checked={formData.monitoring_enabled}
                  onChange={(e) => setFormData({...formData, monitoring_enabled: e.target.checked})}
                  className="rounded border-brand-border bg-slate-900 text-brand-primary focus:ring-0"
                />
                <label htmlFor="edit_monitoring_enabled" className="text-slate-300 font-medium cursor-pointer">Enable active background ICMP monitoring</label>
              </div>

              {/* Edit SNMP Configuration Accordion */}
              <div className="border-t border-brand-border/40 pt-4 mt-2">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-semibold text-slate-300">SNMP Configuration</span>
                  <div className="flex items-center gap-1.5">
                    <input 
                      type="checkbox" 
                      id="edit_snmp_enabled"
                      checked={formData.snmp_enabled}
                      onChange={(e) => setFormData({...formData, snmp_enabled: e.target.checked})}
                      className="rounded border-brand-border bg-slate-900 text-brand-primary focus:ring-0"
                    />
                    <label htmlFor="edit_snmp_enabled" className="text-slate-400 font-medium cursor-pointer">Enable SNMP</label>
                  </div>
                </div>

                {formData.snmp_enabled && (
                  <div className="grid grid-cols-2 gap-3 mt-3 p-3 bg-slate-900/60 rounded-lg border border-brand-border/40 animate-in fade-in-50 duration-200">
                    <div className="flex flex-col gap-1">
                      <label className="text-slate-400 text-2xs font-medium">Version</label>
                      <select 
                        value={formData.snmp_version}
                        onChange={(e) => setFormData({...formData, snmp_version: e.target.value})}
                        className="bg-slate-900 border border-brand-border rounded p-1.5 text-white focus:outline-none text-2xs"
                      >
                        <option value="v2c">v2c</option>
                        <option value="v3">v3 (Coming Soon)</option>
                      </select>
                    </div>
                    <div className="flex flex-col gap-1">
                      <label className="text-slate-400 text-2xs font-medium">Community String</label>
                      <input 
                        type="text" 
                        placeholder="public"
                        value={formData.snmp_community}
                        onChange={(e) => setFormData({...formData, snmp_community: e.target.value})}
                        className="bg-slate-900 border border-brand-border rounded p-1.5 text-white focus:outline-none text-2xs"
                      />
                    </div>
                    <div className="flex flex-col gap-1">
                      <label className="text-slate-400 text-2xs font-medium">Port</label>
                      <input 
                        type="number" 
                        min="1"
                        max="65535"
                        value={formData.snmp_port}
                        onChange={(e) => setFormData({...formData, snmp_port: e.target.value})}
                        className="bg-slate-900 border border-brand-border rounded p-1.5 text-white focus:outline-none text-2xs font-mono"
                      />
                    </div>
                    <div className="flex flex-col gap-1">
                      <label className="text-slate-400 text-2xs font-medium">Poll Interval (s)</label>
                      <input 
                        type="number" 
                        min="5"
                        max="3600"
                        value={formData.snmp_polling_interval}
                        onChange={(e) => setFormData({...formData, snmp_polling_interval: e.target.value})}
                        className="bg-slate-900 border border-brand-border rounded p-1.5 text-white focus:outline-none text-2xs font-mono"
                      />
                    </div>
                  </div>
                )}
              </div>

              <button 
                type="submit" 
                className="mt-4 bg-brand-primary hover:bg-indigo-500 text-white font-medium p-2.5 rounded-lg shadow-md transition-all text-xs"
              >
                Save Configurations
              </button>
            </form>
          </div>
        </div>
      )}

      {/* DEVICE DETAILS & TCP SERVICES DIAGNOSTIC MODAL */}
      {showDetailsModal && detailsDevice && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="glass-panel w-full max-w-3xl rounded-xl p-6 flex flex-col gap-4 animate-in fade-in-50 zoom-in-95">
            <div className="flex items-center justify-between border-b border-brand-border pb-3">
              <div>
                <h3 className="text-base font-semibold text-white flex items-center gap-2">
                  <span className={`h-3 w-3 rounded-full ${
                    detailsDevice.status === 'online' ? 'bg-emerald-500' :
                    detailsDevice.status === 'degraded' ? 'bg-amber-500' :
                    'bg-rose-500'
                  }`}></span>
                  {detailsDevice.name} Services & Health
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">{detailsDevice.ip_address} • {detailsDevice.hostname}</p>
              </div>
              <button 
                onClick={() => {
                  setShowDetailsModal(false);
                  setDetailsDevice(null);
                }} 
                className="text-slate-400 hover:text-white"
              >
                ✕
              </button>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-2">
              
              {/* ICMP Health Column */}
              <div className="bg-slate-900/40 p-4 rounded-xl border border-brand-border/60 flex flex-col gap-4">
                <h4 className="text-xs font-semibold text-slate-300 uppercase tracking-wider flex items-center gap-1.5 border-b border-brand-border/40 pb-2">
                  <Activity className="h-4 w-4 text-brand-primary animate-pulse" />
                  ICMP Diagnostics
                </h4>
                
                <div className="grid grid-cols-2 gap-4 text-xs">
                  <div>
                    <span className="text-slate-400 block mb-0.5">Status</span>
                    <span className={`px-2 py-0.5 rounded text-2xs uppercase font-bold inline-block ${
                      detailsDevice.status === 'online' ? 'bg-emerald-500/20 text-emerald-400' :
                      detailsDevice.status === 'degraded' ? 'bg-amber-500/20 text-amber-400' :
                      'bg-rose-500/20 text-rose-400'
                    }`}>
                      {detailsDevice.status}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-400 block mb-0.5">Ping Status</span>
                    <strong className="text-white font-mono text-xs">
                      {detailsDevice.status !== 'offline' ? 'Active' : 'Unreachable'} 
                    </strong>
                  </div>
                  <div>
                    <span className="text-slate-400 block mb-0.5">Monitoring Loop</span>
                    <span className="text-slate-200">{detailsDevice.monitoring_enabled ? 'Enabled' : 'Disabled'}</span>
                  </div>
                  <div>
                    <span className="text-slate-400 block mb-0.5">Last Seen</span>
                    <span className="text-slate-200">{detailsDevice.last_seen ? new Date(detailsDevice.last_seen).toLocaleTimeString() : 'Never'}</span>
                  </div>
                </div>
                
                <div className="mt-auto pt-4 border-t border-brand-border/40 flex justify-between items-center">
                  <span className="text-3xs text-slate-500">ICMP Active Background Poller</span>
                  {hasOperatorRights ? (
                    <button
                      onClick={() => handleManualPing(detailsDevice.id).then(() => {
                        const updated = devices.find(d => d.id === detailsDevice.id);
                        if (updated) setDetailsDevice(updated);
                      })}
                      disabled={pingingId === detailsDevice.id}
                      className="bg-slate-800 hover:bg-brand-primary text-slate-200 hover:text-white px-3 py-1.5 rounded-lg text-3xs font-semibold shadow transition-all inline-flex items-center gap-1.5 disabled:opacity-50"
                    >
                      {pingingId === detailsDevice.id ? <RefreshCw className="h-3 w-3 animate-spin" /> : <Play className="h-3 w-3" />}
                      Ping Now
                    </button>
                  ) : (
                    <span className="text-[10px] text-slate-500 italic bg-slate-900/40 px-2 py-1 rounded">Read-only diagnostic view</span>
                  )}
                </div>
              </div>

              {/* TCP Services Column */}
              <div className="bg-slate-900/40 p-4 rounded-xl border border-brand-border/60 flex flex-col gap-3 min-h-[220px]">
                <div className="flex items-center justify-between border-b border-brand-border/40 pb-2">
                  <h4 className="text-xs font-semibold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
                    <Settings className="h-4 w-4 text-brand-secondary" />
                    TCP Services
                  </h4>
                  {hasOperatorRights && (
                    <button
                      onClick={() => handleCheckPortsNow(detailsDevice.id)}
                      disabled={checkingPorts || !detailsDevice.monitoring_enabled}
                      className="bg-brand-secondary hover:bg-cyan-500 text-white px-2.5 py-1 rounded text-3xs font-semibold shadow transition-all flex items-center gap-1 disabled:opacity-50"
                    >
                      {checkingPorts ? <RefreshCw className="h-2.5 w-2.5 animate-spin" /> : <Play className="h-2.5 w-2.5" />}
                      Check Ports Now
                    </button>
                  )}
                </div>

                {detailsDevice.tcp_ports && detailsDevice.tcp_ports.length > 0 ? (
                  <div className="overflow-y-auto max-h-[140px] text-3xs">
                    <table className="w-full text-left border-collapse">
                      <thead>
                        <tr className="border-b border-brand-border/60 text-slate-400 font-semibold uppercase">
                          <th className="py-1.5">Port</th>
                          <th className="py-1.5">Service</th>
                          <th className="py-1.5">Status</th>
                          <th className="py-1.5 text-right">Response</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-brand-border/30">
                        {devicePortsStatus.map((pStat, idx) => (
                          <tr key={`${detailsDevice.id}-port-${pStat.port}-${idx}`} className="text-slate-300">
                            <td className="py-1.5 font-mono font-medium">{pStat.port}</td>
                            <td className="py-1.5 text-slate-400">{getPortServiceName(pStat.port)}</td>
                            <td className="py-1.5">
                              <span className={`px-1.5 py-0.5 rounded-sm font-semibold uppercase tracking-wider text-[8px] ${
                                pStat.status === 'open' ? 'bg-emerald-500/20 text-emerald-400' :
                                pStat.status === 'closed' ? 'bg-rose-500/20 text-rose-400' :
                                pStat.status === 'timeout' ? 'bg-amber-500/20 text-amber-400' :
                                'bg-slate-800 text-slate-500'
                              }`}>
                                {pStat.status}
                              </span>
                            </td>
                            <td className="py-1.5 text-right font-mono">
                              {pStat.status === 'open' && pStat.response_time_ms ? `${pStat.response_time_ms.toFixed(1)} ms` : '—'}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="flex-1 flex flex-col items-center justify-center text-center py-6 text-slate-500">
                    <p>No TCP ports configured for monitoring.</p>
                    <p className="mt-1 text-[10px]">Use the input below to configure ports.</p>
                  </div>
                )}
              </div>

            </div>

            {/* TCP Port Quick Configuration Inline Form */}
            {hasAdminRights && (
              <div className="mt-4 pt-4 border-t border-brand-border/40 flex flex-col gap-2">
                <label className="text-xs font-semibold text-slate-300">Configure TCP Ports for Active Monitoring</label>
                <div className="flex gap-2">
                  <input 
                    type="text" 
                    placeholder="e.g. 22, 80, 443 (comma separated ports)"
                    value={portConfigInput}
                    onChange={(e) => setPortConfigInput(e.target.value)}
                    className="flex-1 bg-slate-900 border border-brand-border rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-brand-primary font-mono"
                  />
                  <button
                    onClick={async () => {
                      const portsArr = portConfigInput
                        .split(',')
                        .map(p => parseInt(p.trim()))
                        .filter(p => !isNaN(p) && p >= 1 && p <= 65535);
                      
                      try {
                        const response = await authFetch(`${BACKEND_URL}/api/v1/devices/${detailsDevice.id}`, {
                          method: 'PUT',
                          body: { tcp_ports: portsArr }
                        });
                        if (!response.ok) throw new Error("Failed to update TCP ports.");
                        showToast("TCP Port configuration updated successfully!");
                        
                        const updatedDevice = { ...detailsDevice, tcp_ports: portsArr };
                        setDetailsDevice(updatedDevice);
                        
                        await handleCheckPortsNow(detailsDevice.id);
                        fetchDevices();
                      } catch (err) {
                        showToast(err.message, false);
                      }
                    }}
                    className="bg-brand-primary hover:bg-indigo-500 text-white text-xs px-4 py-2 rounded-lg font-medium shadow-md transition-all whitespace-nowrap"
                  >
                    Save & Check
                  </button>
                </div>
              </div>
            )}

            {/* SNMP Diagnostics Section */}
            <div className="mt-4 pt-4 border-t border-brand-border/40 flex flex-col gap-3">
              <div className="flex items-center justify-between">
                <h4 className="text-xs font-semibold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
                  <Layers className="h-4 w-4 text-emerald-400" />
                  SNMP Interfaces & Traffic Metrics
                </h4>
                {detailsDevice.snmp_config?.snmp_enabled && hasOperatorRights && (
                  <button
                    onClick={() => handleManualSnmpPoll(detailsDevice.id)}
                    disabled={snmpLoading}
                    className="bg-emerald-600 hover:bg-emerald-500 text-white px-2.5 py-1 rounded text-3xs font-semibold shadow transition-all flex items-center gap-1 disabled:opacity-50"
                  >
                    {snmpLoading ? <RefreshCw className="h-2.5 w-2.5 animate-spin" /> : <Play className="h-2.5 w-2.5" />}
                    Poll SNMP Now
                  </button>
                )}
              </div>

              {!detailsDevice.snmp_config?.snmp_enabled ? (
                <div className="bg-slate-900/20 p-4 rounded-xl border border-brand-border/40 text-center text-xs text-slate-500">
                  SNMP monitoring is not enabled for this device.
                </div>
              ) : snmpLoading && snmpInterfaces.length === 0 ? (
                <div className="py-8 flex flex-col items-center justify-center gap-2">
                  <RefreshCw className="h-6 w-6 text-emerald-500 animate-spin" />
                  <span className="text-3xs text-slate-400">Polling SNMP variables...</span>
                </div>
              ) : snmpError ? (
                <div className="p-3 rounded-lg bg-rose-950/30 border border-rose-900/30 text-xs text-rose-400">
                  <strong>SNMP Status:</strong> Offline / Timeout ({snmpError})
                </div>
              ) : (
                <div className="flex flex-col gap-3">
                  {/* System info from SNMP */}
                  {snmpSystem && (
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-2 text-2xs p-3 bg-slate-900/50 rounded-lg border border-brand-border/40">
                      <div>
                        <span className="text-slate-400 block">SysName:</span>
                        <strong className="text-white truncate block">{snmpSystem.hostname || '—'}</strong>
                      </div>
                      <div>
                        <span className="text-slate-400 block">SysUpTime:</span>
                        <strong className="text-white block">
                          {snmpSystem.uptime ? `${(snmpSystem.uptime / 100).toFixed(0)} seconds` : '—'}
                        </strong>
                      </div>
                      <div className="col-span-1 md:col-span-3 mt-1 pt-1 border-t border-brand-border/20">
                        <span className="text-slate-400 block">Description:</span>
                        <span className="text-slate-300 text-3xs font-mono">{snmpSystem.description || '—'}</span>
                      </div>
                    </div>
                  )}

                  {/* Interfaces Table */}
                  {snmpInterfaces && snmpInterfaces.length > 0 ? (
                    <div className="overflow-x-auto max-h-[180px] text-3xs border border-brand-border/40 rounded-lg bg-slate-950/20">
                      <table className="w-full text-left border-collapse">
                        <thead>
                          <tr className="border-b border-brand-border/60 text-slate-400 font-semibold uppercase bg-slate-900/50">
                            <th className="py-2 px-2">Idx</th>
                            <th className="py-2 px-2">Interface</th>
                            <th className="py-2 px-2">Description</th>
                            <th className="py-2 px-2">Status</th>
                            <th className="py-2 px-2">Speed</th>
                            <th className="py-2 px-2 text-right">In (bps)</th>
                            <th className="py-2 px-2 text-right">Out (bps)</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-brand-border/30">
                          {snmpInterfaces.map((item) => (
                            <tr key={`${detailsDevice.id}-snmp-if-${item.index}`} className="text-slate-300 hover:bg-slate-800/10">
                              <td className="py-1.5 px-2 font-mono">{item.index}</td>
                              <td className="py-1.5 px-2 font-semibold text-slate-200">{item.name}</td>
                              <td className="py-1.5 px-2 truncate max-w-[120px] text-slate-400" title={item.description}>{item.description}</td>
                              <td className="py-1.5 px-2">
                                <span className={`px-1.5 py-0.5 rounded-sm font-bold uppercase tracking-wider text-[8px] ${
                                  item.op_status === 'up' ? 'bg-emerald-500/20 text-emerald-400' :
                                  item.op_status === 'down' ? 'bg-rose-500/20 text-rose-400' :
                                  'bg-slate-800 text-slate-500'
                                }`}>
                                  {item.op_status}
                                </span>
                              </td>
                              <td className="py-1.5 px-2 font-mono">
                                {item.speed ? `${(item.speed / 1000000).toFixed(0)} Mbps` : '—'}
                              </td>
                              <td className="py-1.5 px-2 text-right font-mono text-cyan-400 font-semibold">
                                {item.in_rate_bps ? `${(item.in_rate_bps / 1000).toFixed(1)} Kbps` : '0.0 Kbps'}
                              </td>
                              <td className="py-1.5 px-2 text-right font-mono text-brand-secondary font-semibold">
                                {item.out_rate_bps ? `${(item.out_rate_bps / 1000).toFixed(1)} Kbps` : '0.0 Kbps'}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div className="text-center py-4 text-slate-500 text-3xs">
                      No interfaces retrieved. Click "Poll SNMP Now" to start collecting metrics.
                    </div>
                  )}
                </div>
              )}
            </div>
            
          </div>
        </div>
      )}

      {/* REGISTER NEW USER MODAL */}
      {showAddUserModal && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="glass-panel w-full max-w-md rounded-xl p-6 flex flex-col gap-4 animate-in fade-in-50 zoom-in-95">
            <div className="flex items-center justify-between border-b border-brand-border pb-3">
              <h3 className="text-base font-semibold text-white flex items-center gap-2">
                <UserPlus className="h-5 w-5 text-brand-primary" />
                Register New User Account
              </h3>
              <button onClick={() => setShowAddUserModal(false)} className="text-slate-400 hover:text-white">✕</button>
            </div>
            
            <form onSubmit={handleAddUserSubmit} className="flex flex-col gap-4 text-xs">
              <div className="flex flex-col gap-1.5">
                <label className="text-slate-400 font-medium">Email Address</label>
                <input 
                  type="email" 
                  required
                  placeholder="e.g. employee@netvision.com" 
                  value={userFormData.email}
                  onChange={(e) => setUserFormData({...userFormData, email: e.target.value})}
                  className="bg-slate-900 border border-brand-border rounded-lg p-2.5 text-white focus:outline-none focus:border-brand-primary"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="flex flex-col gap-1.5">
                  <label className="text-slate-400 font-medium">Username</label>
                  <input 
                    type="text" 
                    required
                    placeholder="e.g. john_doe" 
                    value={userFormData.username}
                    onChange={(e) => setUserFormData({...userFormData, username: e.target.value})}
                    className="bg-slate-900 border border-brand-border rounded-lg p-2.5 text-white focus:outline-none focus:border-brand-primary"
                  />
                </div>
                <div className="flex flex-col gap-1.5">
                  <label className="text-slate-400 font-medium">Full Name</label>
                  <input 
                    type="text" 
                    placeholder="e.g. John Doe" 
                    value={userFormData.full_name}
                    onChange={(e) => setUserFormData({...userFormData, full_name: e.target.value})}
                    className="bg-slate-900 border border-brand-border rounded-lg p-2.5 text-white focus:outline-none focus:border-brand-primary"
                  />
                </div>
              </div>

              <div className="flex flex-col gap-1.5">
                <label className="text-slate-400 font-medium">Password</label>
                <input 
                  type="password" 
                  required
                  placeholder="••••••••" 
                  value={userFormData.password}
                  onChange={(e) => setUserFormData({...userFormData, password: e.target.value})}
                  className="bg-slate-900 border border-brand-border rounded-lg p-2.5 text-white focus:outline-none focus:border-brand-primary"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="flex flex-col gap-1.5">
                  <label className="text-slate-400 font-medium">System Role</label>
                  <select 
                    value={userFormData.role}
                    onChange={(e) => setUserFormData({...userFormData, role: e.target.value})}
                    className="bg-slate-900 border border-brand-border rounded-lg p-2.5 text-white focus:outline-none focus:border-brand-primary"
                  >
                    <option value="VIEWER">Viewer (Read-only)</option>
                    <option value="OPERATOR">Operator (Diagnostics/Alerts)</option>
                    <option value="ADMIN">Administrator (Full Access)</option>
                  </select>
                </div>
                <div className="flex flex-col gap-1.5 justify-end pb-3">
                  <div className="flex items-center gap-2">
                    <input 
                      type="checkbox" 
                      id="user_is_active"
                      checked={userFormData.is_active}
                      onChange={(e) => setUserFormData({...userFormData, is_active: e.target.checked})}
                      className="rounded border-brand-border bg-slate-900 text-brand-primary focus:ring-0"
                    />
                    <label htmlFor="user_is_active" className="text-slate-300 font-medium cursor-pointer">Active State</label>
                  </div>
                </div>
              </div>

              <button 
                type="submit" 
                className="mt-2 bg-brand-primary hover:bg-indigo-500 text-white font-medium p-2.5 rounded-lg shadow-md transition-all text-xs"
              >
                Register User
              </button>
            </form>
          </div>
        </div>
      )}

      {/* EDIT USER CONFIGURATIONS MODAL */}
      {showEditUserModal && selectedUser && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="glass-panel w-full max-w-md rounded-xl p-6 flex flex-col gap-4 animate-in fade-in-50 zoom-in-95">
            <div className="flex items-center justify-between border-b border-brand-border pb-3">
              <h3 className="text-base font-semibold text-white flex items-center gap-2">
                <Edit3 className="h-5 w-5 text-brand-primary" />
                Modify User Configurations
              </h3>
              <button 
                onClick={() => {
                  setShowEditUserModal(false);
                  resetUserForm();
                }} 
                className="text-slate-400 hover:text-white"
              >
                ✕
              </button>
            </div>
            
            <form onSubmit={handleEditUserSubmit} className="flex flex-col gap-4 text-xs">
              <div className="flex flex-col gap-1.5">
                <label className="text-slate-400 font-medium">Email Address</label>
                <input 
                  type="email" 
                  required
                  placeholder="e.g. employee@netvision.com" 
                  value={userFormData.email}
                  onChange={(e) => setUserFormData({...userFormData, email: e.target.value})}
                  className="bg-slate-900 border border-brand-border rounded-lg p-2.5 text-white focus:outline-none focus:border-brand-primary"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="flex flex-col gap-1.5">
                  <label className="text-slate-400 font-medium">Username</label>
                  <input 
                    type="text" 
                    required
                    placeholder="e.g. john_doe" 
                    value={userFormData.username}
                    onChange={(e) => setUserFormData({...userFormData, username: e.target.value})}
                    className="bg-slate-900 border border-brand-border rounded-lg p-2.5 text-white focus:outline-none focus:border-brand-primary"
                  />
                </div>
                <div className="flex flex-col gap-1.5">
                  <label className="text-slate-400 font-medium">Full Name</label>
                  <input 
                    type="text" 
                    placeholder="e.g. John Doe" 
                    value={userFormData.full_name}
                    onChange={(e) => setUserFormData({...userFormData, full_name: e.target.value})}
                    className="bg-slate-900 border border-brand-border rounded-lg p-2.5 text-white focus:outline-none focus:border-brand-primary"
                  />
                </div>
              </div>

              <div className="flex flex-col gap-1.5">
                <label className="text-slate-400 font-medium">New Password (leave blank to keep current)</label>
                <input 
                  type="password" 
                  placeholder="••••••••" 
                  value={userFormData.password}
                  onChange={(e) => setUserFormData({...userFormData, password: e.target.value})}
                  className="bg-slate-900 border border-brand-border rounded-lg p-2.5 text-white focus:outline-none focus:border-brand-primary"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="flex flex-col gap-1.5">
                  <label className="text-slate-400 font-medium">System Role</label>
                  <select 
                    value={userFormData.role}
                    onChange={(e) => setUserFormData({...userFormData, role: e.target.value})}
                    className="bg-slate-900 border border-brand-border rounded-lg p-2.5 text-white focus:outline-none focus:border-brand-primary"
                  >
                    <option value="VIEWER">Viewer (Read-only)</option>
                    <option value="OPERATOR">Operator (Diagnostics/Alerts)</option>
                    <option value="ADMIN">Administrator (Full Access)</option>
                  </select>
                </div>
                <div className="flex flex-col gap-1.5 justify-end pb-3">
                  <div className="flex items-center gap-2">
                    <input 
                      type="checkbox" 
                      id="edit_user_is_active"
                      checked={userFormData.is_active}
                      onChange={(e) => setUserFormData({...userFormData, is_active: e.target.checked})}
                      className="rounded border-brand-border bg-slate-900 text-brand-primary focus:ring-0"
                    />
                    <label htmlFor="edit_user_is_active" className="text-slate-300 font-medium cursor-pointer">Active State</label>
                  </div>
                </div>
              </div>

              <button 
                type="submit" 
                className="mt-2 bg-brand-primary hover:bg-indigo-500 text-white font-medium p-2.5 rounded-lg shadow-md transition-all text-xs"
              >
                Save Configurations
              </button>
            </form>
          </div>
        </div>
      )}

      {/* Footer Info */}
      <footer className="w-full border-t border-brand-border/40 py-6 px-6 text-center text-xs text-slate-500 glass-panel mt-auto">
        <p>© 2026 NetVision Network Diagnostic Center. Fully operational and verified with Real ICMP & TCP Poller engines.</p>
      </footer>
    </div>
  );
}

export default App;
