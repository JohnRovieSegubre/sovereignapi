‚# INKDROP MVP ARCHITECTURE SPECIFICATION (v1.0)
Goal: Build a reliable, self-service print kiosk for under $1,500. Core Constraint: Must operate unattended (self-recovery from errors).

## 1. HARDWARE STACK

### A. The "Brain" (User Interface)
*   **Device**: Samsung Galaxy Tab A9+ (or similar mid-range Android).
*   **Requirement**: MUST have NFC (Near Field Communication) for payments.
*   **OS**: Android 13+.
*   **Role**: Runs the "InkDrop Kiosk App," handles file upload, processes payment, sends print command.

### B. The "Engine" (Printer)
*   **Device**: Brother HL-L5200DW (or HL-L6200DW).
*   **Why**:
    *   Workhorse reputation (hard to jam).
    *   Cheap generic toner.
    *   Excellent Network Protocol Support (IPP, LPR, Raw Port 9100).
*   **Role**: Receives raw PCL/PDF data from the tablet.

### C. The "Nervous System" (Connectivity)
*   **Device**: Mobile Hotspot (e.g., Alcatel Linkzone or generic 5G puck) OR a Travel Router with a USB modem.
*   **Role**: Creates a private WPA2 Wi-Fi network inside the cabinet named `InkDrop_Internal`.

---

## 2. SOFTWARE ARCHITECTURE

### A. Kiosk Application (Frontend)
*   **Tech Stack**: Web App (React/HTML5) wrapper or Native Android App.
*   **Payment**: **Stripe Tap to Pay on Android SDK**.
    *   *Decision*: We are bypassing the physical Stripe Terminal Reader M2. The tablet ITSELF is the terminal.
*   **Printing**: **IPP (Internet Printing Protocol)** or Raw TCP (Port 9100).
    *   *Logic*: The app generates a PDF, sends it directly to the Printer's IP address (e.g., `192.168.1.50`) over the local Wi-Fi.

### B. Network Topology (Local Closed Loop)
*   **WAN**: Cellular Data (Sim Card in Tablet or Hotspot).
*   **LAN**: `192.168.x.x` subnet.
*   **Security**: The Printer is NOT exposed to the public internet. Only the Tablet can talk to it.

---

## 3. USER FLOW (Physical Walkthrough)

1.  **Attract**: Screen shows "InkDrop: Tap to Print".
2.  **Upload**: User scans QR code or visits `inkdrop.print` on their phone to upload a file.
3.  **Code**: User gets a 6-digit code.
4.  **Input**: User enters code on the Tablet.
5.  **Preview**: Tablet fetches job metadata (Pages: 5, B&W). Calculates price ($1.25).
6.  **Pay**: Tablet prompts "Tap Card on Screen". User taps Visa/Mastercard.
7.  **Process**: Stripe SDK processes payment via Cellular Data.
8.  **Print**: On Success, Tablet opens socket to `192.168.1.50:9100` and streams print data.
9.  **Collect**: User grabs paper from the output tray (cabinet slot).
‚*cascade08"(4e6c28288310718ade2f91adc3fea3b5a41725ce2Afile:///C:/Users/rovie%20segubre/Downloads/new/ARCHITECTURE_V2.md:.file:///C:/Users/rovie%20segubre/Downloads/new