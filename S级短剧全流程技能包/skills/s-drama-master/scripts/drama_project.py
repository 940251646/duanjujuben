#!/usr/bin/env python3
"""Optional standard-library tools for a drama project; no content quality scoring."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


TEMPLATE = Path(__file__).resolve().parents[1] / 'assets' / 'project-template.json'
# Accept both the legacy local name ``EP001.md`` and the collision-proof
# multi-season name ``S01-EP001.md``.  The parent season directory remains the
# source of truth; an optional filename season is checked for consistency.
EPISODE = re.compile(r'(?:S(\d{2})-)?EP(\d{3,})\.md$')
SCENE = re.compile(r'^##\s+EP\d+-S\d+\b', re.M)
SPOKEN = re.compile(r'^(?:[^#【\[|：:]{1,40}(?:【[^】]*】|（[^）]*）)?|【(?:旁白|系统音)[^】]*】)[：:](.*)$')
META = ('目标时长', '当前时长', '出场', '目标', '场景', '人物', '实际时长', '总字数')


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(value, dict):
        raise ValueError(f'Expected an object: {path}')
    return value


def save_new(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='\n') as handle:
        handle.write(text)


def season_specs(config: dict) -> list[dict]:
    """Normalize legacy single-season and explicit multi-season configurations."""
    raw = config.get('seasons')
    if isinstance(raw, list) and raw:
        declared = config.get('season_count', len(raw))
        if isinstance(declared, int) and not isinstance(declared, bool) and len(raw) != declared:
            raise ValueError('season_count must match the number of seasons entries.')
        specs = []
        for index, item in enumerate(raw, 1):
            if not isinstance(item, dict):
                raise ValueError('Each seasons entry must be an object.')
            spec = dict(item)
            spec.setdefault('season_id', f'S{index:02}')
            spec.setdefault('season_number', index)
            spec.setdefault('episode_count', config.get('total_episodes', 120))
            specs.append(spec)
        return specs
    count = config.get('season_count', 1)
    if not isinstance(count, int) or isinstance(count, bool) or count < 1:
        raise ValueError('season_count must be a positive integer.')
    counts = config.get('season_episode_counts')
    if not isinstance(counts, list) or len(counts) != count:
        counts = [config.get('total_episodes', 120)] * count
    return [
        {'season_id': f'S{index:02}', 'season_number': index,
         'episode_count': counts[index-1]}
        for index in range(1, count + 1)
    ]


def _season_budget(config: dict, spec: dict) -> dict:
    budget = dict(config.get('runtime_budget', {}))
    budget.update(spec.get('runtime_budget', {}) or {})
    budget.setdefault('max_total_seconds', 8400)
    budget.setdefault('opening_target_seconds', 150)
    budget.setdefault('later_target_seconds', 65)
    budget.setdefault('opening_min_seconds', 120)
    budget.setdefault('opening_max_seconds', 180)
    budget.setdefault('later_min_seconds', 60)
    budget.setdefault('later_max_seconds', 90)
    return budget


def _season_label(season: int, episode: int, multi: bool):
    if isinstance(season, str) and season.startswith('S'):
        season = int(season[1:])
    return f'S{season:02}-EP{episode:03}' if multi else episode


def episode_files(project: Path, config: dict | None = None) -> dict[tuple[int, int], Path]:
    """Read legacy root episodes and/or seasons/Sxx/episodes files."""
    config = config or {}
    specs = season_specs(config) if config else [{'season_number': 1, 'episode_count': 0}]
    result: dict[tuple[int, int], Path] = {}
    for spec in specs:
        season = int(spec.get('season_number', 1))
        season_dir = project / 'seasons' / f'S{season:02}' / 'episodes'
        root_dir = project / 'episodes' if season == 1 else None
        # A legacy root directory is accepted as S01. If both layouts exist,
        # read both and reject duplicate episode numbers instead of silently
        # choosing one and hiding a possible overwrite.
        dirs = []
        if season_dir.exists():
            dirs.append(season_dir)
        if root_dir is not None and root_dir.exists():
            dirs.append(root_dir)
        for directory in dirs:
            if directory is None or not directory.exists():
                continue
            for path in sorted(directory.glob('*.md')):
                match = EPISODE.fullmatch(path.name)
                if not match:
                    raise ValueError(f'Unexpected episode filename: {path.name}')
                file_season = match.group(1)
                if file_season is not None and int(file_season) != season:
                    raise ValueError(f'Filename season does not match directory: {path.name}')
                number = int(match.group(2))
                key = (season, number)
                if number < 1 or key in result:
                    raise ValueError(f'Duplicate or invalid episode number: {key}')
                result[key] = path
    return result


def script_body(text: str) -> str:
    # Review notes are separated from the actual script by the shared template.
    return re.split(r'^---\s*$|^##\s+制作与审稿', text, maxsplit=1, flags=re.M)[0]


def measure(text: str, low_cpm: float = 180, high_cpm: float = 300) -> dict:
    body = script_body(text)
    utterances = []
    layers = {'dialogue': 0, 'inner_voice': 0, 'narration_system': 0}
    for raw in body.splitlines():
        line = raw.strip()
        if line.startswith(META):
            continue
        match = SPOKEN.match(line)
        if not match:
            continue
        words = re.sub(r'\s', '', match.group(1))
        utterances.append(words)
        kind = ('inner_voice' if '【内心' in line or '【心声' in line else
                'narration_system' if line.startswith(('【旁白', '【系统音')) else 'dialogue')
        layers[kind] += len(words)
    count = sum(map(len, utterances))
    return {
        'script_characters_with_punctuation': len(re.sub(r'\s', '', body)),
        'spoken_characters_with_punctuation': count,
        'spoken_layers': layers,
        'scene_count': len(SCENE.findall(body)),
        'estimated_voice_seconds': [round(count / high_cpm * 60, 1), round(count / low_cpm * 60, 1)],
        'timing_note': 'Voice-only estimate; add sequential action and pauses, and account for overlaps. Validate by read-through.',
        'has_episode_end': '【本集结束】' in body,
    }


def inspect(project: Path, low_cpm: float = 180, high_cpm: float = 300) -> dict:
    config = read_json(project / 'project.json')
    specs = season_specs(config)
    files = episode_files(project, config)
    multi = len(specs) > 1
    expected = {(int(s.get('season_number', i)), n)
                for i, s in enumerate(specs, 1)
                for n in range(1, int(s.get('episode_count', 0)) + 1)}
    rows = []
    for (season, number), path in sorted(files.items()):
        row = measure(path.read_text(encoding='utf-8-sig'), low_cpm, high_cpm)
        row.update(season=f'S{season:02}', episode=number,
                   global_episode=f'S{season:02}-EP{number:03}',
                   file=str(path.relative_to(project)))
        rows.append(row)
    missing_pairs = sorted(expected - set(files))
    extra_pairs = sorted(set(files) - expected)
    incomplete_pairs = [(r['season'], r['episode']) for r in rows
                        if not r['has_episode_end'] or r['scene_count'] == 0 or r['spoken_characters_with_punctuation'] == 0]
    label = lambda pair: _season_label(pair[0], pair[1], multi)
    return {
        'project_name': config.get('project_name'),
        'season_count': len(specs),
        'planned_episodes': sum(int(s.get('episode_count', 0)) for s in specs),
        'episode_files': len(files),
        'missing_episodes': [label(pair) for pair in missing_pairs],
        'extra_episodes': [label(pair) for pair in extra_pairs],
        'format_incomplete': [label(pair) for pair in incomplete_pairs],
        'episodes': rows,
        'runtime_budget': runtime_report(config),
        'literary_review': 'Not assessed by this tool.',
    }


def runtime_report(config: dict) -> dict:
    specs = season_specs(config)
    reports = []
    top_allocation = config.get('episode_runtime_seconds')
    for index, spec in enumerate(specs, 1):
        total = int(spec.get('episode_count', config.get('total_episodes', 0)))
        budget = _season_budget(config, spec)
        opening = budget.get('opening_target_seconds', config.get('target_episode_seconds', 150))
        later = budget.get('later_target_seconds', config.get('target_episode_seconds', 65))
        allocation = spec.get('episode_runtime_seconds')
        if allocation is None and len(specs) == 1:
            allocation = top_allocation
        if allocation is None:
            allocation = [opening if i < 3 else later for i in range(total)]
        issues = []
        if not isinstance(allocation, list) or len(allocation) != total:
            reports.append({'season_id': spec.get('season_id', f'S{index:02}'), 'valid': False,
                            'planned_seconds': None,
                            'issues': ['Runtime allocation length must match episode_count.']})
            continue
        for number, seconds in enumerate(allocation, 1):
            prefix = 'opening' if number <= 3 else 'later'
            low = budget.get(prefix+'_min_seconds', 1)
            high = budget.get(prefix+'_max_seconds', float('inf'))
            if not isinstance(seconds, (int, float)) or isinstance(seconds, bool) or not low <= seconds <= high:
                issues.append(f"{spec.get('season_id', f'S{index:02}')}-EP{number:03}: duration outside configured range {low}..{high}.")
        numeric = all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in allocation)
        seconds_total = sum(allocation) if numeric else None
        # 8400 seconds is a hard product rule, even if an input file tries to
        # raise its local budget.  Report the effective cap used for checking.
        configured_maximum = budget.get('max_total_seconds', 8400)
        maximum = min(configured_maximum, 8400) if isinstance(configured_maximum, (int, float)) else 8400
        if isinstance(configured_maximum, (int, float)) and configured_maximum > 8400:
            issues.append(f"{spec.get('season_id', f'S{index:02}')} configured maximum exceeds hard cap 8400.")
        if maximum is not None and seconds_total is not None and seconds_total > maximum:
            issues.append(f"{spec.get('season_id', f'S{index:02}')} runtime {seconds_total} exceeds season budget {maximum}.")
        reports.append({'season_id': spec.get('season_id', f'S{index:02}'), 'valid': not issues,
                        'planned_seconds': seconds_total,
                        'planned_minutes': round(seconds_total/60, 2) if seconds_total is not None else None,
                        'maximum_seconds': maximum, 'issues': issues})
    totals = [r['planned_seconds'] for r in reports]
    valid = all(r['valid'] for r in reports)
    planned = sum(x for x in totals if x is not None) if all(x is not None for x in totals) else None
    first = reports[0] if reports else {'planned_seconds': None, 'maximum_seconds': None, 'issues': ['No season configured.']}
    return {'valid': valid, 'season_count': len(specs), 'planned_seconds': planned,
            'planned_minutes': round(planned/60, 2) if planned is not None else None,
            'maximum_seconds': sum(r.get('maximum_seconds', 0) or 0 for r in reports),
            'season_reports': reports, 'issues': [issue for r in reports for issue in r.get('issues', [])],
            'first_season_seconds': first.get('planned_seconds')}


def initialize(output: Path, name: str, episodes: int | None, seconds: int | None,
               season_count: int | None = None, season_episodes: list[int] | None = None) -> dict:
    if (output / 'project.json').exists() or (output / 'progress.json').exists():
        raise ValueError('Project configuration already exists; choose a new project directory.')
    config = read_json(TEMPLATE)
    config['project_name'] = name
    if episodes is not None and episodes < 1:
        raise ValueError('episodes must be positive.')
    count = season_count if season_count is not None else 1
    if not isinstance(count, int) or isinstance(count, bool) or count < 1:
        raise ValueError('season_count must be positive.')
    if season_episodes is not None:
        if len(season_episodes) != count or any(x < 1 for x in season_episodes):
            raise ValueError('season_episodes must contain one positive count per season.')
        counts = season_episodes
    else:
        counts = [episodes if episodes is not None else config.get('total_episodes', 120)] * count
    config['season_count'] = count
    config['season_episode_counts'] = counts
    config['total_episodes'] = counts[0]
    template_budget = dict(config.get('runtime_budget', {}))
    config['seasons'] = [
        {'season_id': f'S{index:02}', 'season_number': index, 'title': '',
         'episode_count': counts[index-1], 'status': 'planned',
         'runtime_budget': {'max_total_seconds': template_budget.get('max_total_seconds', 8400),
                            'opening_target_seconds': template_budget.get('opening_target_seconds', 150),
                            'later_target_seconds': template_budget.get('later_target_seconds', 65)},
         'season_promise': '', 'carry_in': [], 'carry_out': []}
        for index in range(1, count + 1)
    ]
    if seconds is not None:
        if seconds < 1:
            raise ValueError('seconds must be positive.')
        config['target_episode_seconds'] = seconds
        config['runtime_override_note'] = 'Per-episode override; rebuild the season runtime allocation before writing.'
        # Keep the legacy top-level allocation for a one-season project, and
        # store an independent allocation on every season for multi-season
        # projects so each season is checked against its own 8400-second cap.
        if count == 1:
            config['episode_runtime_seconds'] = [seconds] * config['total_episodes']
        for spec in config['seasons']:
            spec['episode_runtime_seconds'] = [seconds] * int(spec['episode_count'])
    budget = config.get('runtime_budget', {})
    budget['default_total_seconds'] = min(3, config['total_episodes']) * budget.get('opening_target_seconds', 150) + max(0, config['total_episodes']-3) * budget.get('later_target_seconds', 65)
    progress = dict(project_name=name, season_count=count, planned_episodes=sum(counts),
                    seasons=[{'season_id': f'S{index:02}', 'planned_episodes': counts[index-1], 'status': 'planned'} for index in range(1, count+1)],
                    active_season='S01', next_season='S02' if count > 1 else None, canon_version=1,
                    stage='positioning', completed_episodes=[], reviewed_episodes=[], next_episode=1,
                    open_critical_issues=[], completion_status='in_progress')
    # Materialize the collision-proof multi-season workspace up front.  The
    # files themselves are intentionally left empty so initialization never
    # pretends that an episode has been drafted or reviewed.
    created_directories = []
    if count > 1:
        for relative in ('series', 'canon/season-handoffs'):
            (output / relative).mkdir(parents=True, exist_ok=True)
            created_directories.append(relative)
        for index in range(1, count + 1):
            for relative in (
                f'seasons/S{index:02}/episodes',
                f'seasons/S{index:02}/canon',
                f'seasons/S{index:02}/production',
                f'seasons/S{index:02}/review',
                f'seasons/S{index:02}/deliverables',
            ):
                (output / relative).mkdir(parents=True, exist_ok=True)
                created_directories.append(relative)
    save_new(output / 'project.json', json.dumps(config, ensure_ascii=False, indent=2) + '\n')
    save_new(output / 'progress.json', json.dumps(progress, ensure_ascii=False, indent=2) + '\n')
    return {'project': str(output), 'created': ['project.json', 'progress.json'],
            'created_directories': created_directories}


def assemble(project: Path, output: Path, overwrite: bool = False) -> dict:
    report = inspect(project)
    if report['missing_episodes'] or report['extra_episodes'] or report['format_incomplete']:
        raise ValueError('Assembly requires all expected episode files and complete script format. Run inspect for details.')
    if not report['runtime_budget']['valid']:
        raise ValueError('Runtime budget needs correction. Run inspect for details.')
    config = read_json(project / 'project.json')
    files = episode_files(project, config)
    protected = {p.resolve() for p in files.values()} | {(project / 'project.json').resolve(), (project / 'progress.json').resolve()}
    if output.resolve() in protected:
        raise ValueError('Output points to a project source file.')
    title = report['project_name'] or project.name
    multi = len(season_specs(config)) > 1
    chunks = []
    for (season, number), path in sorted(files.items()):
        label = _season_label(season, number, multi)
        if not multi:
            label = f'EP{number:03}'
        body = script_body(path.read_text(encoding='utf-8-sig')).strip()
        # The source may retain a local EP001 heading, but the assembled
        # multi-season manuscript must distinguish S01-EP001 from S02-EP001.
        chunks.append(
            f'## {label}\n\n<!-- source: {path.relative_to(project).as_posix()} -->\n\n{body}'
        )
    combined = f'# {title}｜全剧文学剧本\n\n' + '\n\n---\n\n'.join(chunks) + '\n'
    if overwrite:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(combined, encoding='utf-8')
    else:
        save_new(output, combined)
    return {'output': str(output), 'episodes_assembled': len(files), 'literary_review': 'Requires separate evidence-based review.'}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    init = commands.add_parser('init', help='Create configuration without overwriting an existing project.')
    init.add_argument('--output', type=Path, required=True)
    init.add_argument('--name', required=True)
    init.add_argument('--episodes', type=int)
    init.add_argument('--seconds', type=int)
    init.add_argument('--season-count', type=int,
                      help='Number of seasons to plan (default: 1).')
    init.add_argument('--season-episodes',
                      help='Comma-separated episode counts, one per season (for example 120,100).')
    check = commands.add_parser('inspect', help='List missing episodes and estimate all voice layers.')
    check.add_argument('--project', type=Path, required=True)
    check.add_argument('--low-cpm', type=float, default=180)
    check.add_argument('--high-cpm', type=float, default=300)
    merge = commands.add_parser('assemble', help='Merge all expected complete-format episode files.')
    merge.add_argument('--project', type=Path, required=True)
    merge.add_argument('--output', type=Path, required=True)
    merge.add_argument('--overwrite', action='store_true')
    args = parser.parse_args()
    try:
        if args.command == 'init':
            season_episodes = None
            if args.season_episodes:
                try:
                    season_episodes = [int(item.strip()) for item in args.season_episodes.split(',') if item.strip()]
                except ValueError as error:
                    raise ValueError('--season-episodes must be comma-separated positive integers.') from error
            result = initialize(args.output, args.name, args.episodes, args.seconds,
                                args.season_count, season_episodes)
        elif args.command == 'inspect':
            if not (0 < args.low_cpm <= args.high_cpm):
                raise ValueError('Require 0 < low-cpm <= high-cpm.')
            result = inspect(args.project, args.low_cpm, args.high_cpm)
        else:
            result = assemble(args.project, args.output, args.overwrite)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
