using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;

class SnipTextDesktopLauncher
{
    [STAThread]
    static void Main()
    {
        string desk = Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory);
        string dir = Path.Combine(desk, "SnipText");
        string exe = Path.Combine(dir, "SnipText.exe");
        string dll = Path.Combine(dir, "_internal", "python313.dll");

        if (!File.Exists(exe) || !File.Exists(dll))
        {
            MessageBox.Show(
                "SnipText portable folder is incomplete.\n\n" +
                "Need:\n  Desktop\\SnipText\\SnipText.exe\n  Desktop\\SnipText\\_internal\\\n\n" +
                "Do not copy only the .exe out of that folder.",
                "SnipText",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error);
            return;
        }

        try
        {
            ProcessStartInfo psi = new ProcessStartInfo(exe);
            psi.WorkingDirectory = dir;
            psi.UseShellExecute = true;
            Process.Start(psi);
        }
        catch (Exception ex)
        {
            MessageBox.Show(
                "Failed to start SnipText:\n" + ex.Message,
                "SnipText",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error);
        }
    }
}
