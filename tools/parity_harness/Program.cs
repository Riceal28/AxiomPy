using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Text;
using System.Web.Script.Serialization;
using Axiom;
using ViewModel;

namespace Harness
{
    /// <summary>
    /// Runs a JSON case matrix through the original Axiom generator sources and dumps the
    /// resulting ffmpeg command lines.  Cases are resolved through the VM statics exactly
    /// like the GUI does, so the output is a faithful oracle for the Python port.
    /// </summary>
    public static class Program
    {
        private static readonly JavaScriptSerializer Json =
            new JavaScriptSerializer { MaxJsonLength = int.MaxValue, RecursionLimit = 256 };

        private static readonly Dictionary<string, Func<object>> Groups =
            new Dictionary<string, Func<object>>
            {
                { "Main", () => VM.MainView },
                { "Format", () => VM.FormatView },
                { "Video", () => VM.VideoView },
                { "Audio", () => VM.AudioView },
                { "Subtitle", () => VM.SubtitleView },
                { "FilterVideo", () => VM.FilterVideoView },
                { "FilterAudio", () => VM.FilterAudioView },
                { "Configure", () => VM.ConfigureView },
            };

        private static Dictionary<string, object> CurrentAfterFormat =
            new Dictionary<string, object>();

        public static int Main(string[] args)
        {
            string casesPath = null;
            string outPath = null;
            for (int i = 0; i < args.Length; i++)
            {
                if (args[i] == "--cases" && i + 1 < args.Length) casesPath = args[++i];
                else if (args[i] == "--out" && i + 1 < args.Length) outPath = args[++i];
            }

            if (casesPath == null || outPath == null)
            {
                Console.Error.WriteLine("usage: AxiomParity --cases <cases.json> --out <out.json>");
                return 2;
            }

            var cases = Json.Deserialize<List<Dictionary<string, object>>>(File.ReadAllText(casesPath));
            var results = new List<Dictionary<string, object>>();
            foreach (var item in cases)
            {
                results.Add(RunCase(item));
            }

            File.WriteAllText(outPath, Json.Serialize(results), new UTF8Encoding(false));
            Console.WriteLine("wrote " + results.Count + " goldens to " + outPath);
            return 0;
        }

        private static Dictionary<string, object> RunCase(Dictionary<string, object> item)
        {
            var result = new Dictionary<string, object>();
            string id = item.ContainsKey("id") ? Convert.ToString(item["id"]) : "unnamed";
            result["id"] = id;
            try
            {
                Reset();
                CurrentAfterFormat = Section(item, "afterFormat")
                    .ToDictionary(pair => pair.Key, pair => pair.Value);
                foreach (var pair in Section(item, "state")) SetState(pair.Key, pair.Value);
                foreach (var pair in Section(item, "ffprobe")) SetStatic(typeof(Analyze.FFprobe), pair.Key, pair.Value);
                foreach (var pair in Section(item, "controls")) SetStatic(typeof(Controls.Configure), pair.Key, pair.Value);
                MainWindow.BatchExtCheck();
                if (VM.MainView.Batch_IsChecked)
                {
                    string batchExt = VM.MainView.BatchExtension_Text ?? string.Empty;
                    if (string.IsNullOrWhiteSpace(batchExt) || batchExt == "extension")
                    {
                        MainWindow.inputExt = string.Empty;
                    }
                    else
                    {
                        MainWindow.inputExt = batchExt.StartsWith(".")
                            ? batchExt
                            : "." + batchExt;
                    }
                }
                else if (!string.IsNullOrWhiteSpace(VM.MainView.Input_Text))
                {
                    // The input-path UI seeds this before OutputPath runs.  With an
                    // explicit output directory, OutputPath_SingleFile relies on it
                    // when appending filename tokens.
                    MainWindow.outputFileName_Original =
                        Path.GetFileNameWithoutExtension(VM.MainView.Input_Text);
                }

                result["nulls"] = NullMembers();

                if (item.ContainsKey("preset") && item["preset"] != null)
                {
                    VM.MainView.Preset_SelectedItem = Convert.ToString(item["preset"]);
                    Profiles.Presets.SetPreset();
                    result["preset"] = VM.MainView.Preset_SelectedItem;
                    result["presetState"] = DumpState();
                }

                ResolveControls();
                foreach (var pair in Section(item, "afterControls")) SetState(pair.Key, pair.Value);
                foreach (object path in Items(item, "audio_paths"))
                {
                    string value = Convert.ToString(path);
                    Generate.Audio.Audio.audioFilePathsList.Add(
                        MainWindow.WrapWithQuotes(value));
                    Generate.Audio.Audio.audioFileNamesList.Add(
                        Path.GetFileName(value));
                }
                foreach (object path in Items(item, "subtitles"))
                {
                    string value = Convert.ToString(path);
                    Generate.Subtitle.Subtitle.subtitleFilePathsList.Add(
                        MainWindow.WrapWithQuotes(value));
                    Generate.Subtitle.Subtitle.subtitleFileNamesList.Add(
                        Path.GetFileName(value));
                }
                result["state"] = DumpState();

                if (VM.MainView.Batch_IsChecked == true)
                {
                    Generate.FFmpeg.Batch.Generate_FFmpegArgs();
                }
                else
                {
                    Generate.FFmpeg.Generate_SingleArgs();
                }

                Generate.FFmpeg.ffmpegArgs = Generate.FFmpeg.ffmpegArgs ?? string.Empty;
                result["args"] = Generate.FFmpeg.ffmpegArgs;
                result["sorted"] = Generate.FFmpeg.ffmpegArgsSort;

                MainWindow.scriptText = Generate.FFmpeg.ffmpegArgs;
                if (VM.MainView.AutoSortScript_IsChecked == true)
                {
                    Controls.ScriptView.sort = false;
                    MainWindow.Sort();
                }
                else
                {
                    VM.MainView.ScriptView_Text = Generate.FFmpeg.ffmpegArgs;
                }

                result["script"] = VM.MainView.ScriptView_Text;
                result["messages"] = Dialog.Messages;
            }
            catch (Exception ex)
            {
                result["error"] = ex.GetType().FullName + ": " + ex.Message;
            }

            return result;
        }

        /// <summary>
        /// Snapshot of the resolved control state.  This is the specification the Python
        /// control layer has to reproduce: scalars as-is, item lists as their names.
        /// </summary>
        private static Dictionary<string, object> DumpState()
        {
            var dump = new Dictionary<string, object>();
            foreach (var group in Groups)
            {
                object instance = group.Value();
                foreach (var property in instance.GetType().GetProperties(
                             BindingFlags.Public | BindingFlags.Instance))
                {
                    if (!property.CanRead) continue;
                    object value;
                    try
                    {
                        value = property.GetValue(instance, null);
                    }
                    catch
                    {
                        continue;
                    }

                    string key = group.Key + "." + property.Name;
                    if (value == null)
                    {
                        dump[key] = null;
                    }
                    else if (value is string || value is bool || value is int || value is double)
                    {
                        dump[key] = value;
                    }
                    else if (value is IEnumerable enumerable)
                    {
                        var items = new List<object>();
                        foreach (var item in enumerable)
                        {
                            if (item == null) { items.Add(null); continue; }
                            if (item is string) { items.Add((string)item); continue; }
                            var nameProperty = item.GetType().GetProperty("Name");
                            items.Add(nameProperty != null
                                ? Convert.ToString(nameProperty.GetValue(item, null))
                                : item.ToString());
                        }

                        dump[key] = items;
                    }
                }

                // The ViewModel also exposes plain public fields (e.g. Video_Codec).
                foreach (var field in instance.GetType().GetFields(
                             BindingFlags.Public | BindingFlags.Instance))
                {
                    object value;
                    try
                    {
                        value = field.GetValue(instance);
                    }
                    catch
                    {
                        continue;
                    }

                    string fieldKey = group.Key + "." + field.Name;
                    if (value is string || value is bool || value is int || value is double)
                    {
                        dump[fieldKey] = value;
                    }
                }
            }

            return dump;
        }

        /// <summary>
        /// Replays the control-layer resolution the GUI performs as the user picks a
        /// container, media type, codecs and quality (this is what fills the VM with the
        /// codec argument tables before a command is generated).
        /// </summary>
        private static void ResolveControls()
        {
            Controls.Format.Controls.FormatControls(VM.FormatView.Format_Container_SelectedItem);
            // Fixture hook: simulate the user changing combo boxes after the container
            // was picked (FormatControls would otherwise overwrite the codec defaults).
            foreach (var pair in CurrentAfterFormat) SetState(pair.Key, pair.Value);
            Controls.Format.Controls.MediaTypeControls();
            Controls.Format.Controls.MediaTypeControls_SelectedItems();
            Controls.Format.Controls.CutControls();
            Controls.Format.Controls.AudioStreamControls();

            Controls.Video.Controls.CodecControls(VM.VideoView.Video_Codec_SelectedItem);
            Controls.Video.Controls.EncodingPassControls();
            Controls.Video.Controls.PixelFormatControls(
                VM.FormatView.Format_MediaType_SelectedItem,
                VM.VideoView.Video_Codec_SelectedItem,
                VM.VideoView.Video_Quality_SelectedItem);
            Controls.Video.Controls.OptimizeControls();
            Controls.Video.Controls.QualityControls();
            Controls.Video.Controls.VideoBitRateDisplay(
                VM.VideoView.Video_Quality_Items,
                VM.VideoView.Video_Quality_SelectedItem,
                VM.VideoView.Video_Pass_SelectedItem);

            Controls.Audio.Controls.CodecControls(VM.AudioView.Audio_Codec_SelectedItem);
            Controls.Audio.Controls.QualityControls();
            Controls.Audio.Controls.AudioBitRateDisplay(
                VM.AudioView.Audio_Quality_Items,
                VM.AudioView.Audio_Quality_SelectedItem);

            Controls.Subtitles.Controls.CodecControls(VM.SubtitleView.Subtitle_Codec_SelectedItem);
        }

        /// <summary>
        /// Nullable state that the WPF UI normally initialises (checkboxes, tri-state
        /// toggles).  Reported so the Python port can model the real startup defaults.
        /// </summary>
        private static List<string> NullMembers()
        {
            var names = new List<string>();
            foreach (var group in Groups)
            {
                object instance = group.Value();
                foreach (var property in instance.GetType().GetProperties(
                             BindingFlags.Public | BindingFlags.Instance))
                {
                    if (!property.CanRead) continue;
                    Type type = property.PropertyType;
                    if (Nullable.GetUnderlyingType(type) == null) continue;
                    object value;
                    try
                    {
                        value = property.GetValue(instance, null);
                    }
                    catch
                    {
                        continue;
                    }

                    if (value == null) names.Add(group.Key + "." + property.Name);
                }
            }

            return names;
        }

        private static void Reset()
        {
            ResetGeneratorStatics();
            VM.MainView = new Main();
            VM.FormatView = new Format();
            VM.VideoView = new Video();
            VM.AudioView = new Audio();
            VM.SubtitleView = new Subtitle();
            VM.FilterVideoView = new FilterVideo();
            VM.FilterAudioView = new FilterAudio();
            VM.ConfigureView = new Configure();

            Generate.FFmpeg.ffmpegArgs = null;
            Generate.FFmpeg.ffmpegArgsSort = null;
            Generate.FFmpeg.ffmpeg = string.Empty;
            MainWindow.inputDir = string.Empty;
            MainWindow.inputFileName = string.Empty;
            MainWindow.inputExt = string.Empty;
            MainWindow.input = string.Empty;
            MainWindow.outputDir = string.Empty;
            MainWindow.outputFileName = string.Empty;
            MainWindow.outputFileName_Original = string.Empty;
            MainWindow.outputExt = string.Empty;
            MainWindow.output = string.Empty;
            MainWindow.scriptText = null;
            MainWindow.Format_Container_PreviousItem = null;
            MainWindow.Video_Codec_PreviousItem = null;
            MainWindow.Video_EncodeSpeed_PreviousItem = null;
            MainWindow.Video_Quality_PreviousItem = null;
            MainWindow.Video_Pass_PreviousItem = null;
            MainWindow.Video_Optimize_PreviousItem = null;
            MainWindow.Video_Optimize_Tune_PreviousItem = null;
            MainWindow.Video_Optimize_Profile_PreviousItem = null;
            MainWindow.Video_Optimize_Level_PreviousItem = null;
            MainWindow.Audio_Codec_PreviousItem = null;
            MainWindow.Audio_Stream_PreviousItem = null;
            MainWindow.Audio_Channel_PreviousItem = null;
            MainWindow.Audio_Quality_PreviousItem = null;
            MainWindow.Audio_CompressionLevel_PreviousItem = null;
            MainWindow.Audio_SampleRate_PreviousItem = null;
            MainWindow.Audio_BitDepth_PreviousItem = null;
            MainWindow.Audio_VBR_PreviousChecked = null;
            CropWindow.crop = string.Empty;
            CropWindow.Divisible = false;
            Dialog.Messages = new List<string>();
            Controls.ScriptView.sort = false;
            Controls.Video.Controls.passUserSelected = false;
            Controls.Configure.threads = string.Empty;
        }

        /// <summary>
        /// Clear the generator/filter accumulators the WPF app normally keeps for the
        /// lifetime of a conversion.  Without this, one case's -vf/-af list leaks into
        /// the next case in the same harness process.
        /// </summary>
        private static void ResetGeneratorStatics()
        {
            Type[] types =
            {
                typeof(Generate.FFmpeg),
                typeof(Generate.Format),
                typeof(Generate.Streams),
                typeof(Generate.Video.Codec),
                typeof(Generate.Video.Encoding),
                typeof(Generate.Video.Video),
                typeof(Generate.Video.Size),
                typeof(Generate.Video.Color),
                typeof(Generate.Video.Params),
                typeof(Generate.Video.Quality),
                typeof(Generate.Audio.Codec),
                typeof(Generate.Audio.Quality),
                typeof(Generate.Audio.Channels),
                typeof(Generate.Audio.Audio),
                typeof(Generate.Audio.Metadata),
                typeof(Generate.Subtitle.Subtitle),
                typeof(Generate.Subtitle.Metadata),
                typeof(Filters.Video),
                typeof(Filters.Audio),
            };

            foreach (Type type in types)
            {
                foreach (FieldInfo field in type.GetFields(
                             BindingFlags.Public | BindingFlags.Static))
                {
                    if (field.FieldType == typeof(string))
                        field.SetValue(null, null);
                    else if (field.FieldType == typeof(List<string>))
                        field.SetValue(null, new List<string>());
                }
                foreach (PropertyInfo property in type.GetProperties(
                             BindingFlags.Public | BindingFlags.Static))
                {
                    if (!property.CanWrite) continue;
                    if (property.PropertyType == typeof(string))
                        property.SetValue(null, null, null);
                    else if (property.PropertyType == typeof(List<string>))
                        property.SetValue(null, new List<string>(), null);
                }
            }
        }

        private static IEnumerable<KeyValuePair<string, object>> Section(
            Dictionary<string, object> item, string key)
        {
            if (!item.ContainsKey(key) || item[key] == null) yield break;
            var section = item[key] as Dictionary<string, object>;
            if (section == null) yield break;
            foreach (var pair in section) yield return pair;
        }

        private static IEnumerable<object> Items(Dictionary<string, object> item, string key)
        {
            if (!item.ContainsKey(key) || item[key] == null) yield break;
            var list = item[key] as IEnumerable;
            if (list == null || item[key] is string) yield break;
            foreach (object value in list) yield return value;
        }

        private static void SetState(string dotted, object value)
        {
            int dot = dotted.IndexOf('.');
            if (dot < 0) throw new ArgumentException("state key must be Group.Property: " + dotted);
            string group = dotted.Substring(0, dot);
            string property = dotted.Substring(dot + 1);
            if (!Groups.ContainsKey(group)) throw new ArgumentException("unknown group: " + group);
            SetMember(Groups[group](), property, value);
        }

        private static void SetStatic(Type type, string name, object value)
        {
            SetMember(null, name, value, type);
        }

        private static void SetMember(object instance, string name, object value, Type type = null)
        {
            type = type ?? instance.GetType();
            var flags = BindingFlags.Public | BindingFlags.Instance | BindingFlags.Static;
            var property = type.GetProperty(name, flags);
            if (property != null)
            {
                property.SetValue(instance, Coerce(value, property.PropertyType), null);
                return;
            }

            var field = type.GetField(name, flags);
            if (field != null)
            {
                field.SetValue(instance, Coerce(value, field.FieldType));
                return;
            }

            throw new ArgumentException(string.Format("{0} has no member {1}", type.Name, name));
        }

        private static object Coerce(object value, Type target)
        {
            Type underlying = Nullable.GetUnderlyingType(target) ?? target;
            if (value == null) return null;

            if (typeof(IList).IsAssignableFrom(underlying) && value is IEnumerable && !(value is string))
            {
                var list = (IList)Activator.CreateInstance(underlying);
                foreach (var entry in (IEnumerable)value)
                {
                    list.Add(Coerce(entry, underlying.GetGenericArguments()[0]));
                }
                return list;
            }

            if (underlying == typeof(string)) return Convert.ToString(value);
            if (underlying.IsEnum) return Enum.Parse(underlying, Convert.ToString(value));
            if (underlying == typeof(bool)) return Convert.ToBoolean(value);
            return Convert.ChangeType(value, underlying, CultureInfo.InvariantCulture);
        }
    }
}
