
Automates the process of identifying where a user is physically located by making the Access Point (AP) they are currently associated with blink its LED.

How the Script Works:
	1.	Trigger: The script runs on a recurring schedule (every minute) using a cron timer.
	2.	Client Tracking: It targets a predefined list of MAC addresses (FOLLOW_MAC). It queries the Wireless LAN Controller (WLC) to determine which AP is currently serving these specific clients.
	3.	Context Gathering: For every AP found, the script uses CDP (Cisco Discovery Protocol) to identify the upstream switch, the switch IP address, and the specific physical port the AP is connected to.
	4.	Visual Identification: It triggers the ap name <name> led flash start command, forcing the AP to blink its LED for 60 seconds.
	5.	Logging: It logs the entire event to the system syslog, providing a record of the client's MAC, the AP name, and the switch-port details.

Engineering Use Cases:
	•	Physical Site Surveys: Quickly locating a user or device in a large, high-density environment without needing to manually cross-reference client tables with floor plans.
	•	Troubleshooting: Identifying exactly which physical switch port and AP a specific client is connected to, which is helpful for verifying cabling or investigating port-specific issues.
	•	Asset Mapping: Validating the physical location of APs by correlating the WLC's logical view with the physical hardware.

Technical Considerations:
	•	Performance: Since this script runs every minute and executes multiple CLI commands (including show commands and regex parsing), it is generally lightweight, but in very large environments with thousands of clients, you should monitor the CPU impact on the WLC.
	•	Rate Limiting: The script includes a wait 2 command to account for IOS-XE syslog rate limiting, which is a best practice to ensure the script doesn't fail due to command throttling.
	•	Permissions: This script requires the appropriate privilege level to execute configuration and show commands on the WLC.