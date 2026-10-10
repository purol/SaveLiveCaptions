import sys
import os
import tkinter as tk
import tkinter.messagebox as msgbox
from function.texthook import hook, lc_detect
from function.save import choose_save_dir, close_file
import asyncio

file_handle = None
exit_event = asyncio.Event()
hook_task = None

async def capture(filename, on_status):
    """Surface fatal errors even in the windowed executable (no console)."""
    try:
        try:
            await hook(filename, exit_event, on_status)
        finally:
            await close_file()
    except Exception as e:
        on_status("Error")
        msgbox.showerror("Recording failed", f"Could not save captions to:\n{filename}\n\n{e}")

async def close_all(window):
    global hook_task
    if hook_task is not None:  
        await hook_task
        hook_task = None
    await close_file()
    window.destroy()

def dashboard(loop):
    window = tk.Tk()
    window.title("CatchCaptionsTool")
    window.geometry("60x160")
    window.overrideredirect(True)
    window.wm_attributes("-topmost", True)
    
    if not lc_detect(): 
            msgbox.showerror("Error", "Live Captions Not Found")  
            window.destroy()  
            return
    
    def start_capture():
        global hook_task
        exit_event.clear()  
        start_btn.config(state=tk.DISABLED)
        stop_btn.config(state=tk.NORMAL)  
        try:
            filename = choose_save_dir()
        except Exception as e:
            start_btn.config(state=tk.NORMAL)
            msgbox.showerror("Recording failed", str(e))
            return

        async def run_capture():
            await capture(filename, status.set)
            if not exit_event.is_set():
                start_btn.config(state=tk.NORMAL)

        status.set("Waiting for captions")
        hook_task = loop.create_task(run_capture())
        

    def stop_capture():
        exit_event.set()
        start_btn.config(state=tk.DISABLED)
        stop_btn.config(state=tk.DISABLED)
        loop.create_task(close_all(window))
    
    def start_move(event):
        window.x = event.x
        window.y = event.y
    
    def stop_move(event):
        window.x = None
        window.y = None
    
    def do_move(event):
        deltax = event.x - window.x
        deltay = event.y - window.y
        x = window.winfo_x() + deltax
        y = window.winfo_y() + deltay
        window.geometry(f"+{x}+{y}")
    
    window.bind("<ButtonPress-1>", start_move)
    window.bind("<ButtonRelease-1>", stop_move)
    window.bind("<B1-Motion>", do_move)

    start_btn = tk.Button(window, text="⚫", command=start_capture)
    start_btn.pack(pady=10)
    stop_btn = tk.Button(window, text="◼", command=stop_capture)
    stop_btn.pack(pady=10)
    status = tk.StringVar(value="Ready")
    tk.Label(window, textvariable=status, wraplength=58, font=("Segoe UI", 8)).pack()

    def poll_loop():
        loop.call_soon(loop.stop)
        loop.run_forever()
        window.after(10, poll_loop)

    window.after(10, poll_loop)
    window.mainloop()

def main():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    dashboard(loop)

if __name__ == "__main__":
    main()
