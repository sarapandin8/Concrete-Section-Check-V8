"""Export the supplied project's three actual elastic stage curves for review.

Optional documentation helper (matplotlib); it does not calculate app results.
It reads Generated_Source_Audit.csv from sls_deflect69_real_inputs.py and never
adds an assumed live-load curve. Product plots remain the shared Plotly charts.
"""
from pathlib import Path
import argparse
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from concrete_pmm_pro.visualization.igird_sls53 import COLORS


def run(source, output):
    data = pd.read_csv(source)
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10,
        'axes.labelcolor': '#334155', 'text.color': '#243749', 'axes.edgecolor': '#94a3b8'})
    fig, axes = plt.subplots(1, 3, figsize=(14, 5.25))
    names = ['Transfer stage', 'Construction stage', 'Service stage']
    for ax, stage in zip(axes, names):
        selected = data.loc[data.Stage.eq(stage)]
        group = selected.loc[selected.Curve.eq(selected.Curve.iloc[0])].sort_values('Station x (m)')
        x, y = group['Station x (m)'], group['Deflection (mm)']
        ax.plot(x, y, color=COLORS['top'], lw=2.3, marker='o', ms=2.5,
            label='Net elastic response')
        index = y.abs().idxmax()
        ax.plot(x.loc[index], y.loc[index], marker='D', ms=6, mfc='white', mec=COLORS['governing'], zorder=4)
        ax.annotate(f"+{y.loc[index]:.3f} mm", (x.loc[index], y.loc[index]),
            xytext=(0, 12), textcoords='offset points', ha='center', fontsize=11, fontweight='bold')
        ax.axhline(0, color='#64748b', lw=.9)
        ax.set_xlim(0, float(x.max()))
        ax.set_xticks([0, 5, 10, 15, 20])
        ax.set_xlabel('Distance x (m)')
        ax.set_title(stage.replace(' stage', ''), fontsize=13, fontweight='bold', pad=12)
        ax.grid(color='#dbe2ea', lw=.6)
        ax.set_axisbelow(True)
        ax.spines[['top', 'right']].set_visible(False)
        if stage == 'Service stage':
            bound = min(float(x.max()) * 1000 / 1500, 30.)
            ax.axhline(-bound, color=COLORS['compression'], lw=1.8, ls=(0, (5, 4)),
                label=f'Project LL limit: {bound:.2f} mm')
            ax.set_ylim(-17, 23)
            ax.text(.5, .16, 'LL source missing - REVIEW\nNo train-load curve calculated',
                transform=ax.transAxes, ha='center', va='center', color='#946200', fontsize=9,
                bbox={'facecolor': 'white', 'edgecolor': 'none', 'alpha': .95})
        else:
            ax.set_ylim(-1.5, 23)
        ax.legend(loc='upper center', bbox_to_anchor=(.5, -.20), frameon=False, fontsize=9)
    axes[0].set_ylabel('Deflection δ (mm); upward positive')
    fig.suptitle('20 m girder - actual input JSON32 stage responses', fontsize=16, fontweight='bold', y=.98)
    fig.text(.5, .895, 'Generated-load elastic preview; full span retained. Service LL limit applies to the LL increment only.\nTransfer / Construction project tolerances are not supplied.',
        ha='center', fontsize=10, color='#475569')
    fig.text(.5, .025, 'Railway min(L/1500, 30 mm) is a project criterion requiring owner confirmation. Long-term effects are not calculated.',
        ha='center', fontsize=9, color='#475569')
    fig.subplots_adjust(left=.065, right=.985, top=.81, bottom=.24, wspace=.29)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=160, facecolor='white')
    plt.close(fig)
    print(output, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.source, args.output)
