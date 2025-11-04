using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using System.Reflection;
using System.Text.Json;
using System.Text.Json.Serialization;
using MTGOSDK.API;
using MTGOSDK.API.Collection;
using MTGOSDK.API.Play.History;

var mode = ParseMode(args);
if (mode == ExecutionMode.None)
{
    return;
}

var timings = new Dictionary<string, long>(StringComparer.OrdinalIgnoreCase);
var totalStopwatch = Stopwatch.StartNew();

var jsonOptions = new JsonSerializerOptions
{
    PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
    WriteIndented = true,
    DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull
};

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
Console.WriteLine(JsonSerializer.Serialize(timings, jsonOptions));

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
        _ => ExecutionMode.None,
    };
}

enum ExecutionMode
{
    None = 0,
    Collection,
    History,
    All
}

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
