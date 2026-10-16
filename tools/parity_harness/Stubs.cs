// Headless replacements for the parts of Axiom that live in WPF windows/controls.
using System;
using System.Collections.Generic;
using System.Windows;

namespace Harness
{
    /// <summary>Deterministic stand-in for MessageBox.Show.</summary>
    public static class Dialog
    {
        public static List<string> Messages = new List<string>();

        public static MessageBoxResult Show(string a)
        {
            Messages.Add(a);
            return MessageBoxResult.No;
        }

        public static MessageBoxResult Show(string a, string b)
        {
            Messages.Add(b + ": " + a);
            return MessageBoxResult.No;
        }

        public static MessageBoxResult Show(string a, string b, MessageBoxButton c)
        {
            Messages.Add(b + ": " + a);
            return MessageBoxResult.No;
        }

        public static MessageBoxResult Show(string a, string b, MessageBoxButton c, MessageBoxImage d)
        {
            Messages.Add(b + ": " + a);
            return MessageBoxResult.No;
        }
    }
}

namespace Analyze
{
    /// <summary>FFprobe results are supplied by the case file instead of running ffprobe.</summary>
    public static class FFprobe
    {
        public static string ffprobe = "ffprobe";
        public static string inputFileProperties { get; set; }
        public static string inputVideoCodec { get; set; }
        public static string inputVideoBitRate { get; set; }
        public static string inputAudioCodec { get; set; }
        public static string inputAudioBitRate { get; set; }
        public static string inputSize { get; set; }
        public static string inputDuration { get; set; }
        public static string inputFrameRate { get; set; }
        public static string vEntryType { get; set; }
        public static string aEntryType { get; set; }
        public static string vEntryTypeBatch { get; set; }

        /// <summary>
        /// Mirrors Analyze.FFprobe.CutDuration against the duration supplied by the case
        /// file (the original runs ffprobe here).
        /// </summary>
        public static string CutDuration(string input_Text, bool batch_IsChecked)
        {
            if (string.IsNullOrWhiteSpace(inputDuration))
            {
                return inputDuration;
            }

            TimeSpan span = TimeSpan.FromSeconds(Convert.ToDouble(inputDuration));
            return string.Format(
                "{0:D2}:{1:D2}:{2:D2}.{3:D3}",
                span.Hours,
                span.Minutes,
                span.Seconds,
                span.Milliseconds);
        }
    }
}

namespace Controls
{
    /// <summary>Global control state normally owned by the WPF Settings tab.</summary>
    public static class Configure
    {
        public static string theme = "Axiom";
        public static string threads = string.Empty;
        public static string maxthreads = string.Empty;
        public static string axiomConfFile = string.Empty;
    }

    /// <summary>Script view sort toggle (MainWindow.Sort reads it).</summary>
    public static class ScriptView
    {
        public static bool sort;
    }
}

namespace Profiles
{
    /// <summary>Custom presets are out of scope; keep the call sites inert.</summary>
    public static class Profiles
    {
        public static List<string> customPresetPathsList = new List<string>();

        public static void ImportPreset(string preset)
        {
        }
    }
}

namespace Preview
{
    public static class FFplay
    {
        public static string ffplay = "ffplay";
    }
}

namespace Axiom
{
    /// <summary>Members of MainWindow that only exist to satisfy Log.cs.</summary>
    public partial class MainWindow
    {
        public LogConsole logconsole = new LogConsole();
    }

    public class LogConsole
    {
        public RtbLog rtbLog = new RtbLog();
    }

    /// <summary>RichTextBox stand-in: never instantiated by the harness.</summary>
    public class RtbLog : System.Windows.Controls.RichTextBox
    {
    }

    /// <summary>
    /// The crop window is a WPF-only feature (removed from the Python port).  The crop
    /// generator takes it as a parameter, so a headless placeholder keeps it compiling.
    /// </summary>
    public class CropWindow
    {
        public static string crop = string.Empty;
        public static string CropX = string.Empty;
        public static string CropY = string.Empty;
        public static string CropWidth = string.Empty;
        public static string CropHeight = string.Empty;
        public static bool Divisible;
    }
}
