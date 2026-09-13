"""One command interface. No network calls, true-source inputs or simulator."""
from __future__ import annotations
from pathlib import Path
import sys,argparse,json,subprocess,os
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT/'src'))

def main():
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='cmd',required=True)
    for name in ['prove','test','experiments','figures','paper','verify','all']:s.add_parser(name)
    q=s.add_parser('q1');q.add_argument('--input',type=Path,required=True);q.add_argument('--out',type=Path,default=ROOT/'results/q1_custom.json')
    q=s.add_parser('q2');q.add_argument('--s1',nargs=2,type=float,required=True);q.add_argument('--bearing',type=float,required=True);q.add_argument('--side',type=int,choices=(-1,1),default=1);q.add_argument('--out',type=Path,default=ROOT/'results/q2_custom.json')
    a=p.parse_args()
    def run(file,*extra):
        env=dict(os.environ)
        if file=='run.py':env.pop('Q12_RECORDED_CHILD',None)
        subprocess.run([sys.executable,str(ROOT/file),*extra],cwd=ROOT,check=True,env=env)
    if a.cmd=='prove':
        from q12.proof import verify_all
        r=verify_all(ROOT/'proofs/global_certificate.json')
        print(json.dumps({k:r[k] for k in ['pass','diameter_star_m','station_original_coordinates_m','elapsed_s']},ensure_ascii=False,indent=2));return
    if a.cmd=='test':subprocess.run([sys.executable,'-m','pytest','-q','--junitxml=logs/pytest.xml'],cwd=ROOT,check=True);return
    if a.cmd in ['experiments','figures','paper','verify']:
        run({'experiments':'experiments.py','figures':'plot_figures.py','paper':'build_paper.py','verify':'verify_delivery.py'}[a.cmd]);return
    if a.cmd=='all':
        for command in ['prove','test','experiments','figures','paper','verify']:run('run.py',command)
        return
    if a.cmd=='q1':
        from q12.geometry import Observation,pure_bearing_region
        data=json.loads(a.input.read_text(encoding='utf-8-sig'));obs=[Observation(**x) for x in data['observations']]
        out=pure_bearing_region(obs,eps_deg=data.get('eps_deg',1.)).metrics()
    else:
        from q12.policy import choose_second_point
        out=choose_second_point(a.s1,a.bearing,side=a.side)
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(out,ensure_ascii=False,indent=2))

if __name__=='__main__':
    if os.environ.get('Q12_RECORDED_CHILD') != '1':
        from evidence import recorded_command
        sys.exit(recorded_command())
    main()
