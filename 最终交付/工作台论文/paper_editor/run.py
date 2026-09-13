"""Start the editor with an explicit loopback address."""
import argparse
from pathlib import Path
import uvicorn

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--port',type=int,default=8765)
    args=parser.parse_args()
    from .app import create_app
    uvicorn.run(create_app(Path(__file__).resolve().parent.parent),host='127.0.0.1',port=args.port,workers=1)

if __name__=='__main__':main()
