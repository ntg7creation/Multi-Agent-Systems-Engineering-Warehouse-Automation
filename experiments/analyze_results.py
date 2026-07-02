from __future__ import annotations

import sys
from pathlib import Path
from typing import Iterable

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUTS_ROOT = REPO_ROOT / "experiments" / "outputs"
SUMMARY_DIR = OUTPUTS_ROOT / "summary"
FIGURES_DIR = OUTPUTS_ROOT / "figures"

ALL_RUNS_PATH = SUMMARY_DIR / "all_runs_summary.csv"
ALL_AGENT_PATH = SUMMARY_DIR / "all_agent_metrics.csv"

GROUPED_SCENARIO_LABEL_PATH = SUMMARY_DIR / "grouped_by_scenario_experiment_label.csv"
GROUPED_LABEL_PATH = SUMMARY_DIR / "grouped_by_experiment_label.csv"
GROUPED_CATEGORY_LABEL_PATH = SUMMARY_DIR / "grouped_by_category_experiment_label.csv"
STRESS_SUMMARY_PATH = SUMMARY_DIR / "stress_summary.csv"
UNFINISHED_RUNS_PATH = SUMMARY_DIR / "unfinished_runs.csv"
ERROR_RUNS_PATH = SUMMARY_DIR / "error_runs.csv"

GROUPED_AGENT_LABEL_PATH = SUMMARY_DIR / "grouped_agent_metrics_by_experiment_label.csv"
GROUPED_AGENT_SCENARIO_LABEL_PATH = SUMMARY_DIR / "grouped_agent_metrics_by_scenario_experiment_label.csv"

REPORT_NUMBERS_PATH = SUMMARY_DIR / "report_numbers.md"

NORMAL_SCENARIOS = {
    "simple_one_agent_delivery",
    "default",
    "two_agents_crossing_paths",
    "two_agents_single_slot_crossing",
    "two_agents_four_tasks_balanced",
    "two_agents_six_tasks_uneven",
    "three_agents_nine_tasks_sustained",
    "four_agents_central_intersection",
    "four_agents_dual_aisle_opposing_flow",
    "four_agents_adjacent_access_cluster",
    "five_agents_asymmetric_detours",
    "one_agent_four_deliveries",
    "one_agent_eight_deliveries",
    "blocked_route_replanning",
    "temporary_blocked_wait_replan",
    "adjacent_access_obstacles",
    "one_agent_spiral_escape",
}

STRESS_SCENARIOS = {
    "congested_narrow_corridor",
    "six_agents_corridor_passing_bays",
    "six_agents_merge_to_dispatch",
    "six_agents_twelve_tasks_hotspots",
    "eight_agents_dense_crossing",
    "ten_agents_twenty_tasks_stress",
    "one_agent_maze_to_center",
}

RUN_NUMERIC_COLUMNS = [
    "seed",
    "max_steps",
    "agents",
    "tasks",
    "ticks",
    "completed_tasks",
    "task_completion_rate",
    "throughput",
    "avg_task_completion_time",
    "total_waits",
    "total_blocked_moves",
    "total_replans",
    "collision_preventions",
    "avg_utility",
    "social_welfare",
]

RUN_METRIC_COLUMNS = [
    "ticks",
    "completed_tasks",
    "task_completion_rate",
    "throughput",
    "avg_task_completion_time",
    "total_waits",
    "total_blocked_moves",
    "total_replans",
    "collision_preventions",
    "avg_utility",
    "social_welfare",
]

EXPECTED_RUN_COLUMNS = {
    "run_id",
    "experiment_label",
    "scenario",
    "seed",
    "max_steps",
    "finished",
    "termination_reason",
    *RUN_METRIC_COLUMNS,
}

AGENT_NUMERIC_COLUMNS = [
    "seed",
    "tasks_completed",
    "total_actions",
    "useful_actions",
    "efficiency",
    "wait_count",
    "failed_movement_count",
    "replanning_count",
    "actual_path_length",
    "average_delivery_time",
    "path_inefficiency",
    "utility_score",
]

AGENT_METRIC_COLUMNS = [
    "tasks_completed",
    "total_actions",
    "useful_actions",
    "efficiency",
    "wait_count",
    "failed_movement_count",
    "replanning_count",
    "actual_path_length",
    "average_delivery_time",
    "path_inefficiency",
    "utility_score",
]

EXPECTED_AGENT_COLUMNS = {
    "run_id",
    "experiment_label",
    "scenario",
    "seed",
    "agent_id",
    *AGENT_METRIC_COLUMNS,
}


def fail(message: str) -> None:
    print(f"ERROR: {message}")
    raise SystemExit(1)


def ensure_input_files() -> tuple[Path, Path | None]:
    if not ALL_RUNS_PATH.exists():
        fail(f"Required file not found: {ALL_RUNS_PATH}")

    agent_path = ALL_AGENT_PATH if ALL_AGENT_PATH.exists() else None
    if agent_path is None:
        print(f"WARNING: Optional file not found: {ALL_AGENT_PATH}")

    return ALL_RUNS_PATH, agent_path


def ensure_required_columns(df: pd.DataFrame, required: set[str], file_path: Path) -> None:
    missing = sorted(required - set(df.columns))
    if missing:
        fail(
            "Missing required columns in "
            f"{file_path}: {', '.join(missing)}"
        )


def parse_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    text = str(value).strip().lower()
    return text in {"true", "1", "yes", "y", "t"}


def to_numeric_columns(df: pd.DataFrame, columns: Iterable[str]) -> pd.DataFrame:
    for col in columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def classify_scenario(scenario: object) -> str:
    name = str(scenario)
    if name in NORMAL_SCENARIOS:
        return "normal"
    if name in STRESS_SCENARIOS:
        return "stress"
    return "other"


def aggregate_with_stats(
    df: pd.DataFrame,
    group_cols: list[str],
    metric_cols: list[str],
) -> pd.DataFrame:
    grouped = (
        df.groupby(group_cols, dropna=False)
        .agg(
            runs=("run_id", "count"),
            finished_runs=("finished_bool", "sum"),
            **{f"{metric}_mean": (metric, "mean") for metric in metric_cols},
            **{f"{metric}_std": (metric, "std") for metric in metric_cols},
        )
        .reset_index()
    )
    grouped["finished_rate"] = grouped["finished_runs"] / grouped["runs"]
    std_cols = [f"{metric}_std" for metric in metric_cols]
    grouped[std_cols] = grouped[std_cols].fillna(0.0)
    return grouped


def save_horizontal_bar(
    df: pd.DataFrame,
    value_col: str,
    title: str,
    output_path: Path,
    xlabel: str,
) -> None:
    if df.empty:
        return

    plot_df = df.copy()
    plot_df["label"] = plot_df["scenario"].astype(str) + " | " + plot_df["experiment_label"].astype(str)
    plot_df = plot_df.sort_values(value_col, ascending=True)

    fig_height = max(6, 0.32 * len(plot_df) + 2)
    plt.figure(figsize=(14, fig_height))
    plt.barh(plot_df["label"], plot_df[value_col])
    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel("scenario | experiment_label")
    plt.tight_layout()
    plt.savefig(output_path, dpi=200)
    plt.close()


def save_vertical_bar(
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    title: str,
    output_path: Path,
    ylabel: str,
) -> None:
    if df.empty:
        return

    plot_df = df.sort_values(x_col)
    labels = plot_df[x_col].astype(str)

    width = max(8, len(plot_df) * 1.2)
    plt.figure(figsize=(width, 6))
    plt.bar(labels, plot_df[y_col])
    plt.title(title)
    plt.xlabel(x_col)
    plt.ylabel(ylabel)
    if len(labels) > 4:
        plt.xticks(rotation=35, ha="right")
    plt.tight_layout()
    plt.savefig(output_path, dpi=200)
    plt.close()


def format_number(value: object, ndigits: int = 4) -> str:
    if pd.isna(value):
        return "n/a"
    if isinstance(value, (int, float)):
        return f"{value:.{ndigits}f}"
    return str(value)


def build_overall_lines(grouped_label: pd.DataFrame) -> list[str]:
    lines: list[str] = []
    for _, row in grouped_label.sort_values("experiment_label").iterrows():
        lines.append(f"### {row['experiment_label']}")
        lines.append(f"- mean social welfare: {format_number(row['social_welfare_mean'])}")
        lines.append(f"- mean average utility: {format_number(row['avg_utility_mean'])}")
        lines.append(f"- mean task completion rate: {format_number(row['task_completion_rate_mean'])}")
        lines.append(f"- mean throughput: {format_number(row['throughput_mean'])}")
        lines.append(f"- mean waits: {format_number(row['total_waits_mean'])}")
        lines.append(f"- mean blocked movements: {format_number(row['total_blocked_moves_mean'])}")
        lines.append(f"- mean replans: {format_number(row['total_replans_mean'])}")
        lines.append(f"- finished rate: {format_number(row['finished_rate'])}")
        lines.append("")
    return lines


def top_lines(df: pd.DataFrame, value_col: str, ascending: bool, n: int = 5) -> list[str]:
    if df.empty:
        return ["- n/a"]

    sorted_df = df.sort_values(value_col, ascending=ascending).head(n)
    lines: list[str] = []
    for _, row in sorted_df.iterrows():
        lines.append(
            "- "
            f"{row['scenario']} | {row['experiment_label']}: "
            f"{format_number(row[value_col])}"
        )
    return lines


def generate_report_numbers(
    all_runs_df: pd.DataFrame,
    analysis_df: pd.DataFrame,
    grouped_label: pd.DataFrame,
    grouped_category_label: pd.DataFrame,
    grouped_scenario_label: pd.DataFrame,
    unfinished_df: pd.DataFrame,
    error_df: pd.DataFrame,
) -> None:
    labels = sorted(all_runs_df["experiment_label"].dropna().astype(str).unique().tolist())
    scenarios = sorted(all_runs_df["scenario"].dropna().astype(str).unique().tolist())

    seeds = pd.to_numeric(all_runs_df["seed"], errors="coerce")
    seed_min = int(seeds.min()) if seeds.notna().any() else None
    seed_max = int(seeds.max()) if seeds.notna().any() else None

    lines: list[str] = []
    lines.append("# Validation Report Numbers")
    lines.append("")

    lines.append("## Dataset Overview")
    lines.append(f"- total runs: {len(all_runs_df)}")
    lines.append(f"- successful runs: {len(all_runs_df) - len(error_df)}")
    lines.append(f"- error runs: {len(error_df)}")
    lines.append(f"- number of scenarios: {len(scenarios)}")
    lines.append(f"- experiment labels found: {', '.join(labels) if labels else 'n/a'}")
    if seed_min is not None and seed_max is not None:
        lines.append(f"- seeds range: {seed_min} to {seed_max}")
    else:
        lines.append("- seeds range: n/a")
    lines.append(f"- number of unfinished/max_steps runs: {len(unfinished_df)}")
    lines.append("")

    lines.append("## Overall Comparison")
    lines.extend(build_overall_lines(grouped_label))

    lines.append("## Normal Scenarios Summary")
    normal_rows = grouped_category_label[grouped_category_label["scenario_category"] == "normal"]
    if normal_rows.empty:
        lines.append("- n/a")
    else:
        for _, row in normal_rows.sort_values("experiment_label").iterrows():
            lines.append(
                "- "
                f"{row['experiment_label']}: "
                f"social_welfare_mean={format_number(row['social_welfare_mean'])}, "
                f"task_completion_rate_mean={format_number(row['task_completion_rate_mean'])}, "
                f"throughput_mean={format_number(row['throughput_mean'])}, "
                f"finished_rate={format_number(row['finished_rate'])}"
            )
    lines.append("")

    lines.append("## Stress Scenarios Summary")
    stress_rows = grouped_category_label[grouped_category_label["scenario_category"] == "stress"]
    if stress_rows.empty:
        lines.append("- n/a")
    else:
        for _, row in stress_rows.sort_values("experiment_label").iterrows():
            lines.append(
                "- "
                f"{row['experiment_label']}: "
                f"social_welfare_mean={format_number(row['social_welfare_mean'])}, "
                f"task_completion_rate_mean={format_number(row['task_completion_rate_mean'])}, "
                f"throughput_mean={format_number(row['throughput_mean'])}, "
                f"finished_rate={format_number(row['finished_rate'])}"
            )
    lines.append("")

    lines.append("## Best and Worst Scenarios")
    lines.append("- top 5 scenario/experiment_label combinations by social welfare:")
    lines.extend(top_lines(grouped_scenario_label, "social_welfare_mean", ascending=False, n=5))
    lines.append("- bottom 5 scenario/experiment_label combinations by social welfare:")
    lines.extend(top_lines(grouped_scenario_label, "social_welfare_mean", ascending=True, n=5))
    lines.append("- scenarios with most waits:")
    lines.extend(top_lines(grouped_scenario_label, "total_waits_mean", ascending=False, n=5))
    lines.append("- scenarios with most blocked movements:")
    lines.extend(top_lines(grouped_scenario_label, "total_blocked_moves_mean", ascending=False, n=5))
    lines.append("- scenarios with most replans:")
    lines.extend(top_lines(grouped_scenario_label, "total_replans_mean", ascending=False, n=5))
    lines.append("")

    lines.append("## Unfinished Runs")
    if unfinished_df.empty:
        lines.append("- No max_steps reached runs found.")
    else:
        unfinished_grouped = (
            unfinished_df.groupby(["scenario", "experiment_label"], dropna=False)
            .agg(runs=("run_id", "count"))
            .reset_index()
            .sort_values(["runs", "scenario", "experiment_label"], ascending=[False, True, True])
        )
        lines.append("- scenarios where max_steps was reached:")
        for _, row in unfinished_grouped.iterrows():
            lines.append(
                f"- {row['scenario']} | {row['experiment_label']}: {int(row['runs'])} runs"
            )
    lines.append("")

    lines.append("## Notes for Validation Report")
    if grouped_label.empty:
        lines.append("- Not enough data to derive notes.")
    else:
        best_label_row = grouped_label.sort_values("social_welfare_mean", ascending=False).iloc[0]
        lines.append(
            "- "
            f"{best_label_row['experiment_label']} has the highest mean social welfare "
            f"({format_number(best_label_row['social_welfare_mean'])})."
        )

        if not stress_rows.empty and not normal_rows.empty:
            normal_sw = normal_rows["social_welfare_mean"].mean()
            stress_sw = stress_rows["social_welfare_mean"].mean()
            if pd.notna(normal_sw) and pd.notna(stress_sw):
                direction = "lower" if stress_sw < normal_sw else "higher"
                lines.append(
                    "- "
                    f"Stress scenarios show {direction} social welfare than normal scenarios "
                    f"(stress={format_number(stress_sw)}, normal={format_number(normal_sw)})."
                )

            normal_wait = normal_rows["total_waits_mean"].mean()
            stress_wait = stress_rows["total_waits_mean"].mean()
            normal_blocked = normal_rows["total_blocked_moves_mean"].mean()
            stress_blocked = stress_rows["total_blocked_moves_mean"].mean()
            normal_replans = normal_rows["total_replans_mean"].mean()
            stress_replans = stress_rows["total_replans_mean"].mean()

            lines.append(
                "- "
                f"Under stress, waits={format_number(stress_wait)} vs normal={format_number(normal_wait)}, "
                f"blocked={format_number(stress_blocked)} vs normal={format_number(normal_blocked)}, "
                f"replans={format_number(stress_replans)} vs normal={format_number(normal_replans)}."
            )

            normal_tcr = normal_rows["task_completion_rate_mean"].mean()
            stress_tcr = stress_rows["task_completion_rate_mean"].mean()
            lines.append(
                "- "
                f"Task completion rate normal={format_number(normal_tcr)} and stress={format_number(stress_tcr)}."
            )

        if unfinished_df.empty:
            lines.append("- No scenarios failed to complete within max_steps.")
        else:
            unfinished_scenarios = sorted(unfinished_df["scenario"].dropna().astype(str).unique().tolist())
            lines.append(
                "- "
                f"Some scenarios reached max_steps without completion: {', '.join(unfinished_scenarios)}."
            )

    REPORT_NUMBERS_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    SUMMARY_DIR.mkdir(parents=True, exist_ok=True)
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    runs_path, agent_path = ensure_input_files()

    all_runs_df = pd.read_csv(runs_path)
    ensure_required_columns(all_runs_df, EXPECTED_RUN_COLUMNS, runs_path)

    all_runs_df = to_numeric_columns(all_runs_df, RUN_NUMERIC_COLUMNS)
    all_runs_df["finished_bool"] = all_runs_df["finished"].apply(parse_bool)
    all_runs_df["scenario_category"] = all_runs_df["scenario"].apply(classify_scenario)
    all_runs_df["termination_reason"] = all_runs_df["termination_reason"].astype(str)

    error_df = all_runs_df[all_runs_df["termination_reason"] == "error"].copy()
    analysis_df = all_runs_df[all_runs_df["termination_reason"] != "error"].copy()
    unfinished_df = all_runs_df[
        all_runs_df["termination_reason"].eq("max_steps_reached")
        | (~all_runs_df["finished_bool"])
    ].copy()

    error_df.to_csv(ERROR_RUNS_PATH, index=False)
    unfinished_df.to_csv(UNFINISHED_RUNS_PATH, index=False)

    grouped_scenario_label = aggregate_with_stats(
        analysis_df,
        ["scenario", "experiment_label"],
        RUN_METRIC_COLUMNS,
    )
    grouped_label = aggregate_with_stats(
        analysis_df,
        ["experiment_label"],
        RUN_METRIC_COLUMNS,
    )
    grouped_category_label = aggregate_with_stats(
        analysis_df,
        ["scenario_category", "experiment_label"],
        RUN_METRIC_COLUMNS,
    )

    grouped_scenario_label.to_csv(GROUPED_SCENARIO_LABEL_PATH, index=False)
    grouped_label.to_csv(GROUPED_LABEL_PATH, index=False)
    grouped_category_label.to_csv(GROUPED_CATEGORY_LABEL_PATH, index=False)

    stress_summary = grouped_scenario_label[
        grouped_scenario_label["scenario"].isin(STRESS_SCENARIOS)
    ].copy()
    stress_summary.to_csv(STRESS_SUMMARY_PATH, index=False)

    save_vertical_bar(
        grouped_label,
        x_col="experiment_label",
        y_col="social_welfare_mean",
        title="Average Social Welfare by Experiment Label",
        output_path=FIGURES_DIR / "average_social_welfare_by_experiment_label.png",
        ylabel="mean social_welfare",
    )
    save_vertical_bar(
        grouped_label,
        x_col="experiment_label",
        y_col="avg_utility_mean",
        title="Average Utility by Experiment Label",
        output_path=FIGURES_DIR / "average_utility_by_experiment_label.png",
        ylabel="mean avg_utility",
    )

    save_horizontal_bar(
        grouped_scenario_label,
        value_col="task_completion_rate_mean",
        title="Task Completion Rate by Scenario",
        output_path=FIGURES_DIR / "task_completion_rate_by_scenario.png",
        xlabel="mean task_completion_rate",
    )
    save_horizontal_bar(
        grouped_scenario_label,
        value_col="social_welfare_mean",
        title="Social Welfare by Scenario",
        output_path=FIGURES_DIR / "social_welfare_by_scenario.png",
        xlabel="mean social_welfare",
    )
    save_horizontal_bar(
        grouped_scenario_label,
        value_col="total_waits_mean",
        title="Total Waits by Scenario and Experiment Label",
        output_path=FIGURES_DIR / "total_waits_by_scenario_experiment_label.png",
        xlabel="mean total_waits",
    )
    save_horizontal_bar(
        grouped_scenario_label,
        value_col="total_blocked_moves_mean",
        title="Blocked Moves by Scenario and Experiment Label",
        output_path=FIGURES_DIR / "blocked_moves_by_scenario_experiment_label.png",
        xlabel="mean total_blocked_moves",
    )
    save_horizontal_bar(
        grouped_scenario_label,
        value_col="total_replans_mean",
        title="Replans by Scenario and Experiment Label",
        output_path=FIGURES_DIR / "replans_by_scenario_experiment_label.png",
        xlabel="mean total_replans",
    )
    save_horizontal_bar(
        grouped_scenario_label,
        value_col="throughput_mean",
        title="Throughput by Scenario and Experiment Label",
        output_path=FIGURES_DIR / "throughput_by_scenario_experiment_label.png",
        xlabel="mean throughput",
    )

    save_horizontal_bar(
        stress_summary,
        value_col="social_welfare_mean",
        title="Stress Social Welfare Comparison",
        output_path=FIGURES_DIR / "stress_social_welfare_comparison.png",
        xlabel="mean social_welfare",
    )
    save_horizontal_bar(
        grouped_scenario_label,
        value_col="finished_rate",
        title="Finished Rate by Scenario",
        output_path=FIGURES_DIR / "finished_rate_by_scenario.png",
        xlabel="finished_rate",
    )

    generate_report_numbers(
        all_runs_df=all_runs_df,
        analysis_df=analysis_df,
        grouped_label=grouped_label,
        grouped_category_label=grouped_category_label,
        grouped_scenario_label=grouped_scenario_label,
        unfinished_df=unfinished_df,
        error_df=error_df,
    )

    if agent_path is not None:
        agent_df = pd.read_csv(agent_path)
        ensure_required_columns(agent_df, EXPECTED_AGENT_COLUMNS, agent_path)
        agent_df = to_numeric_columns(agent_df, AGENT_NUMERIC_COLUMNS)

        grouped_agent_label = aggregate_with_stats(
            agent_df.assign(finished_bool=True),
            ["experiment_label"],
            AGENT_METRIC_COLUMNS,
        )
        grouped_agent_scenario_label = aggregate_with_stats(
            agent_df.assign(finished_bool=True),
            ["scenario", "experiment_label"],
            AGENT_METRIC_COLUMNS,
        )

        grouped_agent_label.to_csv(GROUPED_AGENT_LABEL_PATH, index=False)
        grouped_agent_scenario_label.to_csv(GROUPED_AGENT_SCENARIO_LABEL_PATH, index=False)

        save_vertical_bar(
            grouped_agent_label,
            x_col="experiment_label",
            y_col="utility_score_mean",
            title="Agent Utility by Experiment Label",
            output_path=FIGURES_DIR / "agent_utility_by_experiment_label.png",
            ylabel="mean utility_score",
        )
        save_vertical_bar(
            grouped_agent_label,
            x_col="experiment_label",
            y_col="efficiency_mean",
            title="Agent Efficiency by Experiment Label",
            output_path=FIGURES_DIR / "agent_efficiency_by_experiment_label.png",
            ylabel="mean efficiency",
        )
        save_vertical_bar(
            grouped_agent_label,
            x_col="experiment_label",
            y_col="wait_count_mean",
            title="Agent Wait Count by Experiment Label",
            output_path=FIGURES_DIR / "agent_wait_count_by_experiment_label.png",
            ylabel="mean wait_count",
        )

    print(f"Summary tables saved to: {SUMMARY_DIR}")
    print(f"Figures saved to: {FIGURES_DIR}")
    print(f"Report saved to: {REPORT_NUMBERS_PATH}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
