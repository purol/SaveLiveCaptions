# Save Live Captions

**Tired of losing live captions on Windows?**  This is a simple tool to save the content of live captions! The saved text document is like following:
><img width="1187" height="477" alt="image" src="https://github.com/user-attachments/assets/78f3a0df-80f3-4e40-bc0e-9137910352c6" />

###  Features

---
- ✨Save live captions to a text file.
- 😃Minimalist floating dashboard.
- **😎Customizable save options. (save location and quality option in `config.py`)**

###  Installation
### Option 1: Quick Start (Executable)
You can download the latest version from the [Releases](../../releases) page.

> [!IMPORTANT]
> **Note on Antivirus Alerts:** If you encounter a malware warning for the `.exe` file, it is likely a **false positive** due to the lack of a digital signature. If you worry about this, try option 2 as follows. 

### Option 2: Run from Source (Recommended for Security)
If you prefer to run the code directly, follow these steps in your bash/PowerShell/cmd:

1. **Clone this repo**:
   ```bash
   git clone https://github.com/LiveCaptionsHelper/SaveLiveCaptions.git
   ```
2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
3. **Run the tool**:
   ```bash
   python src/main.py
   ```
   > **Good News, You can now edit the `src/function/config.py` to modify the quality of saving on your own.**

### Guidelines

---

1. Before you open this application, make sure you already **open the live captions on Windows** (or it will exit automatically). Then double click the `SaveLiveCaptions.exe`. A small dashboard will appear in the top-left corner of your screen. You can drag the background to move this window.

![Dashboard Preview](./assets/dashboard.png)  

2. The **● (Circle)**  button is "start to save captions" and the **■ (Square)** button is "stop and exit the application". 

3. **Start saving:** When you click the circle button, a file dialog will open to choose a save location. If you don't choose the direction, the default location is `~/Documents/captions`. 

   You can start recording before any speech begins. The dashboard shows **Waiting for captions** until caption text becomes available, and **Reconnecting** while retrying UI Automation errors. Recording resumes automatically when the caption UI becomes available. A transcript is created when text is saved; stopping without any captions does not create an empty file. File-saving errors are shown in a dialog.

4. **Stop and exit:** When you click the square button, it stops and exit the application. You can find your captions file `YYYY-MM-DD_HH-MM-SS_captions.txt` in the chosen location like following.

![Captions File Example](./assets/captionsFile.png)

## Testing

After installing `requirements.txt`, run `python -m unittest discover -s tests -v`.
The tests simulate UI Automation controls and use real temporary transcript files;
they do not validate a real Windows Live Captions UI.

Manual Windows checks:

- Launch Live Captions, start recording before speech, wait several seconds, then play audio. Confirm text is saved without restarting SaveLiveCaptions.
- Start recording after captions are already visible and check timestamps, duplicate suppression, and final text after stopping.
- Close and reopen Live Captions during recording, then resume audio. Confirm recording recovers and existing transcript text remains.
- Stop while waiting for the first caption. Confirm the app exits normally without creating an empty transcript.
- Select an unwritable destination and produce captions. Confirm a recording error dialog appears.

## License

This project is licensed under the MIT License.


