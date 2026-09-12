"""Directed, fixed-point rational interval arithmetic (Python integers only).

Endpoints are integers / 10**40. Every multiplication, division and square
root rounds outwards. Trigonometric constants use Machin's formula and
Taylor polynomials with explicit remainder bounds. No binary floating point
enters the proof arithmetic.
"""
from __future__ import annotations
from fractions import Fraction
from dataclasses import dataclass
from math import isqrt, factorial
from functools import lru_cache
SCALE=10**40

def ceil_div(a: int,b: int)->int:
    if b<0:a,b=-a,-b
    return -((-a)//b)

@dataclass(frozen=True)
class IV:
    lo:int
    hi:int
    def __post_init__(self):
        if self.lo>self.hi:raise ValueError('Reversed interval')
    @staticmethod
    def of(x):
        if isinstance(x,IV):return x
        f=Fraction(str(x)) if isinstance(x,float) else Fraction(x)
        return IV(f.numerator*SCALE//f.denominator,ceil_div(f.numerator*SCALE,f.denominator))
    @staticmethod
    def hull(a,b):
        a,b=IV.of(a),IV.of(b);return IV(min(a.lo,b.lo),max(a.hi,b.hi))
    def __add__(self,x):
        x=IV.of(x);return IV(self.lo+x.lo,self.hi+x.hi)
    __radd__=__add__
    def __neg__(self):return IV(-self.hi,-self.lo)
    def __sub__(self,x):return self+-IV.of(x)
    def __rsub__(self,x):return IV.of(x)+-self
    def __mul__(self,x):
        x=IV.of(x);p=[self.lo*x.lo,self.lo*x.hi,self.hi*x.lo,self.hi*x.hi]
        return IV(min(p)//SCALE,ceil_div(max(p),SCALE))
    __rmul__=__mul__
    def __truediv__(self,x):
        x=IV.of(x)
        if x.lo<=0<=x.hi:raise ZeroDivisionError('Interval divisor contains zero')
        vals=[Fraction(a*SCALE,b) for a in (self.lo,self.hi) for b in (x.lo,x.hi)]
        l,h=min(vals),max(vals)
        return IV(l.numerator//l.denominator,ceil_div(h.numerator,h.denominator))
    def __rtruediv__(self,x):return IV.of(x)/self
    def sq(self):
        p=[self.lo*self.lo,self.hi*self.hi]
        return IV(0 if self.lo<=0<=self.hi else min(p)//SCALE,ceil_div(max(p),SCALE))
    def sqrt(self):
        if self.lo<0:raise ValueError('Negative square-root interval')
        a,b=isqrt(self.lo*SCALE),isqrt(self.hi*SCALE)
        return IV(a,b+(b*b<self.hi*SCALE))
    def __pow__(self,n):
        if n<0:return 1/(self**(-n))
        r=IV.of(1)
        for _ in range(n):r=r*self
        return r
    def maxabs(self):return Fraction(max(abs(self.lo),abs(self.hi)),SCALE)
    def endpoints(self):return Fraction(self.lo,SCALE),Fraction(self.hi,SCALE)
    def json(self):
        def fmt(v):
            sign='-' if v<0 else '';v=abs(v)
            return sign+str(v//SCALE)+'.'+str(v%SCALE).zfill(40)
        return [fmt(self.lo),fmt(self.hi)]
    def midpoint(self):return Fraction(self.lo+self.hi,2*SCALE)

def _atan_recip(n,terms=70):
    z=Fraction(1,n);s=Fraction(0)
    for k in range(terms):s+=(-1)**k*z**(2*k+1)/(2*k+1)
    term=(-1)**terms*z**(2*terms+1)/(2*terms+1)
    return IV.hull(s,s+term)

@lru_cache(maxsize=1)
def pi():
    # Alternating arctangent series and Machin: pi=16 atan(1/5)-4 atan(1/239).
    return 16*_atan_recip(5)-4*_atan_recip(239)

def sincos_rad(x:IV):
    """Valid for |x|<=2; proof callers use a reduced angle <=pi/2.
    Horner polynomial, then Lagrange remainder |x|**(2n)/(2n)!.
    """
    x=IV.of(x)
    if x.maxabs()>2:raise ValueError('Reduce the angle before Taylor evaluation')
    z=x.sq();n=35
    c=IV.of(Fraction((-1)**(n-1),factorial(2*n-2)))
    t=IV.of(Fraction((-1)**(n-1),factorial(2*n-1)))
    for k in range(n-2,-1,-1):
        c=c*z+Fraction((-1)**k,factorial(2*k))
        t=t*z+Fraction((-1)**k,factorial(2*k+1))
    sn=x*t
    # Same conservative order-68 Taylor remainder bounds both polynomials.
    rem=IV.of(x.maxabs()**(2*n-1)/factorial(2*n-1))
    return IV(sn.lo-rem.hi,sn.hi+rem.hi),IV(c.lo-rem.hi,c.hi+rem.hi)

@lru_cache(maxsize=10000)
def sincos_deg(deg:Fraction):
    d=Fraction(deg)%360;q=int(d//90);r=d-90*q
    sn,cs=sincos_rad(pi()*r/180)
    return [(sn,cs),(cs,-sn),(-sn,-cs),(-cs,sn)][q]

def sincos_range(lo,hi):
    lo,hi=Fraction(lo),Fraction(hi)
    if hi<lo:raise ValueError('Reversed angular interval')
    if hi-lo>=360:return IV.of(-1)+IV(0,2*SCALE),IV(-SCALE,SCALE)
    vals=[sincos_deg(lo),sincos_deg(hi)]
    for k in range(int(lo//90)-1,int(hi//90)+2):
        if lo<=90*k<=hi:vals.append(sincos_deg(Fraction(90*k)))
    return IV(min(v[0].lo for v in vals),max(v[0].hi for v in vals)),IV(min(v[1].lo for v in vals),max(v[1].hi for v in vals))

def dot(a,b):return a[0]*b[0]+a[1]*b[1]
def cross(a,b):return a[0]*b[1]-a[1]*b[0]
def vecsub(a,b):return [a[i]-b[i] for i in range(2)]
def norm2(a):return a[0].sq()+a[1].sq()
