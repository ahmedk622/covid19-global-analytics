// Power Query (M) for the four tables. Home > Transform data > Manage Parameters > New Parameter:
//   Name: DataFolder   Type: Text   Current value: full path to data\processed\ including the trailing backslash
// Then for each query below: New Source > Blank Query > Advanced Editor, paste the code, name the query as shown.

// ===== Fact_Covid =====
let
    Source = Csv.Document(File.Contents(DataFolder & "Fact_Covid.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed = Table.TransformColumnTypes(Headers, {
        {"Date", type date}, {"ISO_Code", type text},
        {"Confirmed", Int64.Type}, {"Deaths", Int64.Type}, {"Recovered", Int64.Type}, {"Active", Int64.Type},
        {"Daily_Cases", Int64.Type}, {"Daily_Deaths", Int64.Type}, {"Daily_Recoveries", Int64.Type},
        {"Revision_Flag", Int64.Type}, {"Inconsistency_Flag", Int64.Type}
    }, "en-US")
in
    Typed

// ===== Dim_Date =====
let
    Source = Csv.Document(File.Contents(DataFolder & "Dim_Date.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed = Table.TransformColumnTypes(Headers, {
        {"Date", type date}, {"Year", Int64.Type}, {"Quarter", Int64.Type}, {"Year_Quarter", type text},
        {"Month_Number", Int64.Type}, {"Month_Name", type text}, {"Year_Month", type text},
        {"Week_Start", type date}, {"Weekday_Number", Int64.Type}, {"Weekday_Name", type text}, {"Is_Weekend", Int64.Type}
    }, "en-US")
in
    Typed

// ===== Dim_Country =====
let
    Source = Csv.Document(File.Contents(DataFolder & "Dim_Country.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed = Table.TransformColumnTypes(Headers, {
        {"ISO_Code", type text}, {"Country", type text}, {"JHU_Name", type text}, {"ISO2_Code", type text},
        {"Region", type text}, {"Sub_Region", type text}, {"Population", Int64.Type},
        {"Latitude", type number}, {"Longitude", type number}
    }, "en-US")
in
    Typed

// ===== DQ_Checks =====
let
    Source = Csv.Document(File.Contents(DataFolder & "DQ_Checks.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed = Table.TransformColumnTypes(Headers, {
        {"Section", type text}, {"Item", type text}, {"Value", type text}, {"Status", type text}, {"Note", type text}
    })
in
    Typed
