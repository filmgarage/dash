# DASH --- Network Security Best Practices

This guide explains how to deploy DASH safely on a Home Assistant
network. It is written for the person administering the router,
firewall, VLANs, Wi-Fi and Home Assistant host.

DASH is designed to serve lightweight dashboards to wall tablets, photo
frames and other dedicated displays. A display opens a URL and does not
need an interactive login. That convenience is intentional, but it means
network access must be restricted carefully.

> **Important:** A DASH read token is not a substitute for network
> segmentation. In the current design, the published viewer files, skins
> and images under `/dash/` are reachable on TCP port `8092` without a
> token. The token protects the data/API functions. Therefore, restrict
> which client devices can reach port `8092` at the firewall.

This document describes user-side deployment controls. It does not claim
that these controls fix application-level vulnerabilities or replace a
code security review.

## 1. Understand what DASH exposes

DASH uses two separate access paths:

  --------------------------------------------------------------------------------
  Component               Access path                      Intended users
  ----------------------- -------------------------------- -----------------------
  DASH editor             Home Assistant sidebar through   Trusted Home Assistant
                          Ingress                          administrators

  Screen server           Home Assistant host, TCP `8092`  Approved display
                                                           devices

  Published viewer files, `http://HA_ADDRESS:8092/dash/`   No token required in
  skins and images                                         the current version

  Screen data, layouts,   TCP `8092` API and WebSocket     Requires the configured
  pictures, service calls                                  DASH read token
  and live updates                                         
  --------------------------------------------------------------------------------

The editor is exposed through Home Assistant Ingress; it does not use a
separate host port. The screen server is published as TCP port `8092` on
the Home Assistant host.

The screen server uses plain HTTP and WebSocket (`http://` and `ws://`).
Do not treat traffic on this port as encrypted.

### Security consequences

-   Any device that can connect to TCP `8092` may retrieve published
    viewer files, skins and images, even if it does not know the read
    token.
-   A client that also obtains the read token can access the protected
    screen API. Depending on the DASH configuration and published
    layout, this includes entity states and permitted service calls.
-   The current version uses one read token for all screens. It is not
    an individual credential per device.
-   A URL containing the token is a bearer credential: anyone who
    obtains the complete URL may be able to use it.
-   A firewall rule limiting access to approved client IP addresses is
    an important additional control.

## 2. Recommended network design

The preferred deployment is to put dedicated DASH displays in their own
VLAN or otherwise isolated network segment.

Example network plan (replace the example addresses with your own):

  ------------------------------------------------------------------------
  Network / device                           Example Purpose
  --------------------- ---------------------------- ---------------------
  Home Assistant server                 `10.0.10.10` Runs Home Assistant
                                                     and DASH

  Trusted management                  `10.0.10.0/24` Admin computers and
  VLAN                                               trusted
                                                     infrastructure

  DASH display VLAN                   `10.0.30.0/24` Dedicated wall
                                                     tablets and photo
                                                     frames

  Display 1                             `10.0.30.21` Approved DASH client

  Display 2                             `10.0.30.22` Approved DASH client
  ------------------------------------------------------------------------

The important principles are:

1.  Put dedicated displays in a separate VLAN/SSID where practical.
2.  Give each display a stable IP address, preferably with a DHCP
    reservation.
3.  Permit only those display IP addresses to connect to the Home
    Assistant host on TCP `8092`.
4.  Deny the display VLAN access to other internal networks by default.
5.  Do not expose TCP `8092` to the internet.
6.  Do not publish TCP `8092` through a reverse proxy or public tunnel.
7.  Keep Home Assistant administration accessible only from trusted
    management devices.

A separate VLAN is preferable to simply placing displays on the normal
household Wi-Fi. It limits the damage if a display, browser or kiosk
application is compromised.

## 3. Give every display a stable IP address

Create a DHCP reservation for each display in your router or DHCP
server.

For example:

  Device                  Reserved address
  --------------------- ------------------
  Kitchen display             `10.0.30.21`
  Hallway display             `10.0.30.22`
  Living-room display         `10.0.30.23`

Use the device's Wi-Fi or Ethernet MAC address when creating the
reservation. Confirm that the device actually receives the reserved
address.

Avoid relying on a manually configured static IP on the display unless
you manage addressing consistently. A DHCP reservation is usually easier
to audit and change centrally.

Keep a simple inventory containing:

-   Display name and physical location.
-   MAC address.
-   Reserved IP address.
-   DASH layout assigned to the display.
-   Date the device was last checked.

Do not reuse a reserved display address for an untrusted or temporary
device.

## 4. Firewall rules: allow only approved clients

Create firewall rules between the DASH display VLAN and the Home
Assistant network.

### Minimum required rule

Allow:

-   **Source:** the individual reserved IP addresses of approved DASH
    displays.
-   **Destination:** the Home Assistant host IP address.
-   **Protocol:** TCP.
-   **Destination port:** `8092`.
-   **Action:** Allow.

Example:

``` text
ALLOW  10.0.30.21  ->  10.0.10.10  TCP 8092
ALLOW  10.0.30.22  ->  10.0.10.10  TCP 8092
ALLOW  10.0.30.23  ->  10.0.10.10  TCP 8092
```

If your firewall supports address groups, create a group such as
`DASH_DISPLAYS` containing only the reserved display IP addresses. Use
that group as the source in one allow rule.

### Deny everything else from the display VLAN

After the specific allow rule, deny access from the DASH display VLAN
to:

-   Other internal VLANs and LAN subnets.
-   Home Assistant management interfaces and ports, except where
    separately and explicitly required.
-   Router, firewall, switch and access-point management interfaces.
-   NAS devices, computers, printers, cameras and other IoT devices.
-   Other display clients, unless a specific use case requires
    communication between them.

Also deny access from the display VLAN to the Home Assistant host on all
ports other than TCP `8092`, unless another explicitly documented
service is required.

**Rule order matters.** The allow rule for approved display IPs and TCP
`8092` must be evaluated before the broader deny rule. Check how your
firewall handles established/related traffic and inter-VLAN policies.

### Example policy matrix

  -----------------------------------------------------------------------
  Source            Destination       Port / protocol   Policy
  ----------------- ----------------- ----------------- -----------------
  Approved display  Home Assistant    TCP `8092`        Allow
  IPs               host                                

  Other devices in  Home Assistant    Any other port    Deny
  display VLAN      host                                

  Display VLAN      Other internal    Any               Deny
                    VLANs                               

  Display VLAN      Router / network  Any               Deny
                    management                          

  Display VLAN      Other display     Any               Deny, unless
                    clients                             required

  Internet / WAN    Home Assistant    TCP `8092`        Deny
                    host                                

  Internet / WAN    Home Assistant    Any unsolicited   Deny
                    host              inbound           
  -----------------------------------------------------------------------

Do not create a broad rule such as "IoT VLAN → LAN: Allow" just to make
DASH work. DASH screen access should require only the specific TCP port
above.

### Stateful firewall note

The display initiates the HTTP and WebSocket connections to DASH.
Replies travel back over those established connections. A stateful
firewall normally allows the return traffic automatically; you should
not need a separate rule allowing new connections from Home Assistant to
the display.

## 5. Wi-Fi and switch isolation

Where supported, enable client/device isolation on the display SSID or
VLAN.

This can prevent one display from directly connecting to another device
on the same wireless network. It is useful, but it does not replace
inter-VLAN firewall rules.

Recommended settings:

-   Use a dedicated SSID mapped only to the DASH display VLAN.
-   Use WPA2-AES or WPA3 with a strong, unique Wi-Fi password.
-   Disable WPS.
-   Enable wireless client isolation where compatible with your network.
-   Do not use a guest portal that requires user interaction on a kiosk
    display.
-   Do not bridge the display SSID to the trusted LAN.
-   Keep switch ports assigned to the correct VLAN; do not use an
    unrestricted trunk for a display.

If a display uses Ethernet, assign its switch port to the display VLAN
as an access/untagged port. Do not allow the display to choose or tag
arbitrary VLANs.

## 6. DNS, DHCP and NTP

A display may need a small number of infrastructure services to operate
reliably.

Allow only the services your network actually uses:

-   **DHCP:** to obtain its reserved address, gateway and DNS settings.
-   **DNS:** to resolve the Home Assistant hostname, if you use one
    instead of an IP address.
-   **NTP:** to keep the display clock accurate, if required by the
    device.

Prefer infrastructure services provided by your router or designated
servers. Do not allow unrestricted access to every internal DNS or time
server.

If the DASH start URL uses a numeric Home Assistant IP address, DNS may
not be needed for DASH itself. The browser or device may still need DNS
for operating-system functions.

If the display must reach the internet for time synchronisation or
updates, allow only the necessary outbound access where your firewall
supports it. Do not assume that unrestricted internet access is required
for DASH to display a local dashboard.

## 7. Home Assistant host and port configuration

DASH publishes the screen server on TCP port `8092` of the Home
Assistant host.

Recommended actions:

-   Keep the Home Assistant host on a trusted server/management VLAN.
-   Use a DHCP reservation or a properly managed static address for Home
    Assistant.
-   Keep TCP `8092` reachable only from approved display IP addresses
    and trusted administration devices that need to test it.
-   Do not create a router port-forward for TCP `8092`.
-   Do not expose TCP `8092` through Nginx Proxy Manager, another
    reverse proxy, a public tunnel or a cloud relay.
-   Do not assume that putting the Home Assistant web interface behind
    HTTPS also protects port `8092`. The screen server is a separate
    listener.
-   Review router, firewall and reverse-proxy rules after network
    changes and DASH updates.

The DASH editor remains available through Home Assistant Ingress.
Protect Home Assistant itself with strong user authentication and
restrict administrative access to trusted devices.

## 8. Configure the DASH read token carefully

Set a strong, unique read token in the DASH app configuration before
using any screen.

Recommended practice:

-   Generate the token with a cryptographically secure password
    generator.
-   Use at least 24 randomly generated characters; longer is preferable.
-   Do not use a human-readable phrase, Wi-Fi password or Home Assistant
    password.
-   Never reuse the token for another application.
-   Do not put the token in public documentation, screenshots, support
    posts or shared notes.
-   Store the token in a password manager or another appropriately
    protected location.
-   Treat the complete screen URL as a secret because it contains the
    token.
-   Replace the token immediately if a display is lost, sold, reset or
    no longer trusted.

The current DASH version uses one shared read token for all screens.
Changing it means updating the start URL on every display.

The token protects the data/API functions; it does **not** hide the
published viewer files from devices that can reach TCP `8092`. This is
why IP-based firewall restrictions remain essential.

## 9. Use the least privilege in DASH options

Only publish the entities and actions that a screen actually needs.

Recommended configuration approach:

-   Keep `allow_domains` as small as practical.
-   Prefer explicit `allow_entities` entries when only a few entities
    are needed.
-   Keep `exclude_domains` and `exclude_entities` in place for sensitive
    entities.
-   Keep `read_services` to the minimum required for the dashboard.
-   Do not enable lock, unlock, alarm or other security-sensitive
    services for a shared or unattended display.
-   Do not assume that excluding a direct service also blocks every
    script or button that might trigger that action. Review the complete
    action path before exposing controls.
-   A screen can start any script, button or scene it is allowed to use,
    and a script can do more than its name says. A script that switches a
    light can also switch a lock or an alarm. Read what a script does in
    Home Assistant before you put it, or a button that runs it, on a layout.
    The HA App cannot check the actions of a script for you.
-   Use read-only dashboards wherever possible.
-   Test controls with non-critical devices before using them for
    important equipment.

A display in a public or semi-public area should normally show
information only. If it needs controls, restrict those controls to
low-impact actions.

## 10. Secure the display device itself

A display is a network client with access to the DASH service. Treat it
as a small dedicated computer.

Recommended measures:

-   Use a supported operating system and keep it updated.
-   Keep the kiosk browser, such as Fully Kiosk Browser, updated.
-   Disable Android developer options and ADB when they are no longer
    needed.
-   Do not leave USB debugging or network ADB enabled in normal
    operation.
-   Set a device PIN or other local protection for administrative
    settings.
-   Prevent ordinary users from leaving the kiosk application, where
    appropriate.
-   Do not install unrelated apps or grant unnecessary permissions.
-   Do not store Home Assistant administrator credentials on the
    display.
-   Physically secure displays in public or accessible areas.
-   Remove old displays from the Wi-Fi network, DHCP reservations and
    firewall address groups when decommissioned.

A kiosk lock-down improves physical security, but it does not replace
VLAN isolation or firewall rules.

## 11. HTTP, HTTPS and trusted networks

The current screen server communicates over plain HTTP and WebSocket.
The read token and dashboard data are therefore not encrypted in
transit.

For this reason:

-   Use DASH only on a trusted, controlled local network.
-   Do not use public Wi-Fi or an untrusted shared network for screen
    access.
-   Do not expose the service directly to the internet.
-   Do not assume that a long token makes unencrypted traffic safe.

If you need to transport DASH traffic across an untrusted network, use a
properly configured private VPN or a TLS-terminating reverse proxy on a
trusted internal boundary. Configure WebSocket proxying correctly and
ensure that the firewall prevents clients from bypassing the proxy and
connecting directly to port `8092`.

Do not make a public reverse-proxy route to DASH merely to avoid
configuring local routing. Remote access should be provided through a
VPN with authenticated users/devices and restrictive access policies.

## 12. Monitoring and periodic review

Network security is not a one-time configuration.

Review the following regularly:

-   Check firewall logs for unexpected sources connecting to TCP `8092`.
-   Confirm that only the approved display IP addresses can reach the
    port.
-   Check DHCP leases against your display inventory.
-   Remove unused firewall address-group entries and reservations.
-   Review the published layouts and the entities they expose.
-   Review `read_services` and other allow/exclude settings after
    configuration changes.
-   Replace the shared read token if it may have been disclosed.
-   Keep Home Assistant, DASH, the host operating system, router,
    firewall and display software updated.
-   Review router port-forwarding and reverse-proxy rules after network
    changes.
-   Test that an ordinary client on another VLAN cannot open
    `http://HA_ADDRESS:8092/dash/`.

Do not rely solely on a successful token-protected API test. Also test
the unauthenticated static viewer path, because the published files are
intentionally reachable without the token in the current version.

## 13. Example: UniFi network policy

The names of menus vary between UniFi Network versions, but the policy
should implement the same controls.

1.  Create a dedicated network/VLAN for DASH displays, for example VLAN
    ID `30`.
2.  Create a dedicated Wi-Fi SSID and map it to that VLAN.
3.  Create DHCP reservations for each display.
4.  Create an IP/address group named `DASH_DISPLAYS` containing only
    those reserved IP addresses.
5.  Create an allow rule from `DASH_DISPLAYS` to the Home Assistant host
    IP, TCP destination port `8092`.
6.  Create a deny rule from the display VLAN to the Home Assistant host
    for other ports.
7.  Create deny rules from the display VLAN to other internal networks
    and network-management addresses.
8.  Ensure the rules are ordered so the specific DASH allow rule is
    evaluated before broader deny rules.
9.  Enable client/device isolation on the display SSID if compatible
    with the devices.
10. Verify the policy from both an approved display and an ordinary
    device on another VLAN.

If your UniFi gateway uses zone-based firewall policies, express the
same policy between the appropriate source and destination zones. Do not
copy legacy LAN IN/LAN LOCAL rule instructions blindly; use the policy
model actually present in your UniFi Network version.

## 14. Verification checklist

Perform these checks after installation and after significant network
changes.

### From an approved display

-   [ ] The display receives its reserved IP address.
-   [ ] The DASH start URL loads the intended published layout.
-   [ ] Live state updates work.
-   [ ] Any intended controls work.
-   [ ] The display does not need access to the Home Assistant
    administration interface.

### From an ordinary client on another VLAN

-   [ ] TCP `8092` on the Home Assistant host is blocked.
-   [ ] The client cannot load `/dash/` or a published viewer file.
-   [ ] The client cannot reach other devices in the display VLAN.
-   [ ] The client cannot reach router or switch management interfaces
    through the display VLAN.

### From an unapproved device on the display VLAN

-   [ ] It cannot connect to the Home Assistant host on TCP `8092`.
-   [ ] It cannot access other internal VLANs.
-   [ ] It cannot reach other display clients, if client isolation is
    enabled.

### From outside the home network

-   [ ] No router port-forward exists for TCP `8092`.
-   [ ] No public reverse-proxy or tunnel route exposes DASH.
-   [ ] Remote access, if required, uses a VPN and remains restricted to
    approved devices.

### DASH configuration

-   [ ] A long, unique read token is configured.
-   [ ] The token is not reused elsewhere.
-   [ ] The token is not shared in public or untrusted locations.
-   [ ] Only necessary entities are allowed.
-   [ ] Only necessary screen services are enabled.
-   [ ] Sensitive controls are excluded from unattended displays.
-   [ ] Published layouts contain no private information that should be
    hidden from other clients on the display network.

## 15. Security limitations and responsibility

These recommendations reduce network exposure, but they do not guarantee
that DASH, Home Assistant, the display operating system or the network
infrastructure is free of vulnerabilities.

In particular, the current DASH version has these design limitations:

-   Published viewer files, skins and images are accessible without a
    read token to any client that can reach TCP `8092`.
-   One shared read token is used for all screens.
-   The screen server uses unencrypted HTTP and WebSocket.
-   A client with access to the screen network may attempt to inspect or
    copy a display's URL and token.

Use the application only on networks you administer and trust. Keep the
network rules restrictive, publish only appropriate content, and test
all controls before relying on them.

**Never expose TCP port `8092` directly to the public internet.**

## 16. Maintaining this guide

This guide describes DASH HA App 0.7.3 and contract 8.6. Update it in the same change as any of these:

- A new or changed port, endpoint or path that a screen or a visitor can reach (for example `/image`, section 4.1
  of the contract).
- A change to authentication: per-device tokens, token rotation, or a login on the screen server.
- HTTPS or encryption on the screen server. Sections 11 and 15 must then be rewritten.
- A change in what is published without a token, such as the viewer files or skins under `/dash/`.
- A change in the default `read_services`, `allow_domains` or `exclude_*` options (section 9).
- A new HA App version that changes any of the above.

Record the version the guide was last reviewed against here:

- Last reviewed: DASH HA App 0.7.3, contract 8.6.
