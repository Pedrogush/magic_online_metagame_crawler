using System;
using System.Collections;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using System.Reflection;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Globalization;
using System.Threading;
using System.Threading.Tasks;
using MTGOSDK.API;
using MTGOSDK.API.Collection;
using MTGOSDK.API.Play;
using MTGOSDK.API.Play.Games;
using MTGOSDK.API.Play.Tournaments;
using MTGOSDK.API.Play.History;
using MTGOSDK.API.Play.Leagues;

var mode = ParseMode(args);
if (mode == ExecutionMode.None)
{
    return;
}

var jsonOptions = new JsonSerializerOptions
{
    PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
    WriteIndented = true,
    DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
};

if (mode == ExecutionMode.Watch)
{
    RunWatchLoopAsync(jsonOptions).GetAwaiter().GetResult();
    return;
}

var timings = new Dictionary<string, long>(StringComparer.OrdinalIgnoreCase);
var totalStopwatch = Stopwatch.StartNew();

CollectionSnapshot? collectionSnapshot = null;
HistorySnapshot? historySnapshot = null;

if (mode is ExecutionMode.Collection or ExecutionMode.All)
{
    collectionSnapshot = Measure("collectionMs", GetCollectionSnapshot, timings);
}

if (mode is ExecutionMode.History or ExecutionMode.All)
{
    historySnapshot = Measure("historyMs", GetHistorySnapshot, timings);
}

totalStopwatch.Stop();
timings["totalMs"] = totalStopwatch.ElapsedMilliseconds;

var payload = new BridgePayload(
    DateTimeOffset.UtcNow,
    mode.ToString(),
    collectionSnapshot,
    historySnapshot,
    timings
);

var serialized = JsonSerializer.Serialize(payload, jsonOptions);

// Observed timings with ~2,290 cards and 270 matches (2024-xx-xx):
// collectionMs ≈ 3_728, historyMs ≈ 17_280, totalMs ≈ 21_009
Console.WriteLine(serialized);

static T Measure<T>(string key, Func<T> factory, IDictionary<string, long> timings)
{
    var sw = Stopwatch.StartNew();
    try
    {
        return factory();
    }
    finally
    {
        sw.Stop();
        timings[key] = sw.ElapsedMilliseconds;
    }
}

static CollectionSnapshot GetCollectionSnapshot()
{
    try
    {
        var collection = CollectionManager.Collection;
        var frozen = collection.GetFrozenCollection ?? Array.Empty<CardQuantityPair>();
        var items = frozen
            .Select(card => new CollectionCard(card.Id, card.Name, card.Quantity))
            .ToList();

        return new CollectionSnapshot(
            collection.Id,
            string.IsNullOrWhiteSpace(collection.Name) ? "Collection" : collection.Name,
            collection.ItemCount,
            collection.MaxItems,
            items,
            null
        );
    }
    catch (Exception ex)
    {
        return new CollectionSnapshot(
            0,
            null,
            0,
            0,
            Array.Empty<CollectionCard>(),
            ex.Message
        );
    }
}

static HistorySnapshot GetHistorySnapshot()
{
    var items = new List<HistoryEntry>();
    bool historyLoaded;
    string? error = null;

    try
    {
        historyLoaded = HistoryManager.HistoryLoaded;
        if (!historyLoaded)
        {
            // Attempt to read history for the active user to populate cache.
            HistoryManager.ReadGameHistory();
            historyLoaded = HistoryManager.HistoryLoaded;
        }

        if (historyLoaded)
        {
            foreach (var item in HistoryManager.Items)
            {
                var entry = MapHistoryItem(item);
                if (entry != null)
                {
                    items.Add(entry);
                }
            }
        }
    }
    catch (Exception ex)
    {
        historyLoaded = false;
        error = ex.Message;
    }

    return new HistorySnapshot(historyLoaded, items, error);
}

static HistoryEntry? MapHistoryItem(object? item)
{
    if (item is null)
    {
        return null;
    }

    switch (item)
    {
        case HistoricalMatch match:
            return new HistoryEntry(
                "match",
                match.Id,
                match.StartTime,
                match.Opponents.Select(o => Normalize(o?.Name)).Where(n => n.Length > 0).ToList(),
                match.GameWins,
                match.GameLosses,
                match.GameTies,
                match.GameIds.ToList(),
                null,
                null,
                null
            );

        case HistoricalTournament tournament:
            var summaries = tournament.Matches
                .Select(MapMatchSummary)
                .Where(summary => summary != null)
                .Cast<MatchSummary>()
                .ToList();

            return new HistoryEntry(
                "tournament",
                tournament.Id,
                tournament.StartTime,
                Array.Empty<string>(),
                null,
                null,
                null,
                null,
                summaries,
                tournament.MatchWins,
                tournament.MatchLosses
            );

        case HistoricalItem<dynamic>.Default fallback:
            return new HistoryEntry(
                "historicalItem",
                fallback.Id,
                fallback.StartTime,
                Array.Empty<string>(),
                null,
                null,
                null,
                null,
                null,
                null,
                null
            );

        default:
            return new HistoryEntry(
                item.GetType().Name,
                SafeGet<int>(item, "Id"),
                SafeGet(item, "StartTime", DateTime.MinValue),
                Array.Empty<string>(),
                null,
                null,
                null,
                null,
                null,
                null,
                null
            );
    }
}

static MatchSummary? MapMatchSummary(HistoricalMatch match)
{
    var opponents = match.Opponents
        .Select(o => Normalize(o?.Name))
        .Where(n => n.Length > 0)
        .ToList();

    return new MatchSummary(
        match.Id,
        match.StartTime,
        match.GameWins,
        match.GameLosses,
        match.GameTies,
        opponents,
        match.GameIds.ToList()
    );
}

static string Normalize(string? value) =>
    string.IsNullOrWhiteSpace(value) ? string.Empty : value.Trim();

static T SafeGet<T>(object target, string propertyName, T defaultValue = default!)
{
    if (target is null)
    {
        return defaultValue;
    }

    try
    {
        var value = target.GetType().GetProperty(propertyName, BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic)?.GetValue(target);
        if (value is null)
        {
            return defaultValue;
        }

        if (value is T typed)
        {
            return typed;
        }

        return (T)Convert.ChangeType(value, typeof(T));
    }
    catch
    {
        return defaultValue;
    }
}

static async Task RunWatchLoopAsync(JsonSerializerOptions options, TimeSpan? interval = null)
{
    interval ??= TimeSpan.FromMilliseconds(500);
    Console.OutputEncoding = Encoding.UTF8;

    using var cts = new CancellationTokenSource();
    Console.CancelKeyPress += (_, args) =>
    {
        args.Cancel = true;
        cts.Cancel();
    };

    while (!cts.IsCancellationRequested)
    {
        WatchSnapshot snapshot;
        try
        {
            var timers = GetChallengeTimers();
            snapshot = new WatchSnapshot(DateTimeOffset.UtcNow, timers, null);
        }
        catch (Exception ex)
        {
            snapshot = new WatchSnapshot(
                DateTimeOffset.UtcNow,
                Array.Empty<ChallengeTimerSnapshot>(),
                ex.Message
            );
        }

        var line = JsonSerializer.Serialize(snapshot, options);
        Console.WriteLine(line);

        try
        {
            await Task.Delay(interval.Value, cts.Token);
        }
        catch (TaskCanceledException)
        {
            break;
        }
    }
}

static IReadOnlyList<ChallengeTimerSnapshot> GetChallengeTimers()
{
    var results = new List<ChallengeTimerSnapshot>();
    
    foreach (var evt in SnapshotEnumerable(EventManager.JoinedEvents))
    {
        switch (evt)
        {
            case null:
                continue;
            case Match match:
                continue;
            case Tournament tournament:
                double? seconds = null;
                var tournamentTimer = SafeGet<object>(evt, "TimeRemaining");
                seconds = ConvertToDouble(SafeGet(tournamentTimer, "TotalSeconds", 0.0));
                results.Add(new ChallengeTimerSnapshot(
                    EventId: SafeGet(evt, "Id", SafeGet(evt, "EventId", "No event Id found")),
                    Description: SafeGet(evt, "Description", "No event description found"),
                    Format: SafeGet(evt, "Format", "No format found"),
                    RemainingSeconds: seconds,
                    State: SafeGet(evt, "State", SafeGet(evt, "Status", "No state found"))
                ));
                continue;
            case League league:
                continue;
        }
    }
    return results;
}

static IReadOnlyList<object?> SnapshotEnumerable(object? candidate)
{
    if (candidate is null)
    {
        return Array.Empty<object?>();
    }

    if (candidate is string or byte[])
    {
        return new object?[] { candidate };
    }

    if (candidate is IEnumerable enumerable)
    {
        var list = new List<object?>();
        foreach (var item in enumerable)
        {
            list.Add(item);
        }
        return list;
    }

    return new object?[] { candidate };
}


static double? ConvertToDouble(object? value)
{
    if (value is null)
    {
        return null;
    }

    switch (value)
    {
        case double d:
            return d;
        case float f:
            return f;
        case decimal dec:
            return (double)dec;
        case int i:
            return i;
        case long l:
            return l;
        case TimeSpan span:
            return span.TotalSeconds;
        case string s when double.TryParse(s, NumberStyles.Float, CultureInfo.InvariantCulture, out var parsed):
            return parsed;
        default:
            try
            {
                var converted = Convert.ToDouble(value, CultureInfo.InvariantCulture);
                return converted;
            }
            catch
            {
                return null;
            }
    }
}

static ExecutionMode ParseMode(string[] args)
{
    if (args.Length == 0)
    {
        return ExecutionMode.None;
    }

    var token = args[0]?.Trim() ?? string.Empty;
    token = token.TrimStart('-', '/');
    if (token.Length == 0)
    {
        return ExecutionMode.None;
    }

    return token.ToLowerInvariant() switch
    {
        "collection" or "collect" => ExecutionMode.Collection,
        "history" or "matches" => ExecutionMode.History,
        "all" or "both" => ExecutionMode.All,
        "watch" or "monitor" => ExecutionMode.Watch,
        _ => ExecutionMode.None,
    };
}

enum ExecutionMode
{
    None = 0,
    Collection,
    History,
    All,
    Watch,
}

public sealed record ChallengeTimerSnapshot(
    string? EventId,
    string? Description,
    string? Format,
    double? RemainingSeconds,
    string? State
);

public sealed record WatchSnapshot(
    DateTimeOffset Timestamp,
    IReadOnlyList<ChallengeTimerSnapshot> ChallengeTimers,
    string? Error
);

public sealed record CollectionCard(int Id, string Name, int Quantity);

public sealed record CollectionSnapshot(
    int Id,
    string? Name,
    int ItemCount,
    int MaxItems,
    IReadOnlyList<CollectionCard> Items,
    string? Error
);

public sealed record MatchSummary(
    int Id,
    DateTime StartTime,
    int GameWins,
    int GameLosses,
    int GameTies,
    IReadOnlyList<string> Opponents,
    IReadOnlyList<int> GameIds
);

public sealed record HistoryEntry(
    string Kind,
    int Id,
    DateTime StartTime,
    IReadOnlyList<string> Opponents,
    int? GameWins,
    int? GameLosses,
    int? GameTies,
    IReadOnlyList<int>? GameIds,
    IReadOnlyList<MatchSummary>? Matches,
    int? MatchWins,
    int? MatchLosses
);

public sealed record HistorySnapshot(
    bool HistoryLoaded,
    IReadOnlyList<HistoryEntry> Items,
    string? Error
);

public sealed record BridgePayload(
    DateTimeOffset Timestamp,
    string Mode,
    CollectionSnapshot? Collection,
    HistorySnapshot? History,
    IReadOnlyDictionary<string, long> Timings
);
