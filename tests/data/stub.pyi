X: int

def f(): ...

class C:
    ...

class B:
    ...

class A:
    def f(self) -> int:
        ...

    def g(self) -> str: ...

def g():
    ...

def h(): ...

# output
X: int

def f(): ...

class C: ...
class B: ...

class A:
    def f( self ) -> int: ...
    def g( self ) -> str: ...

def g(): ...
def h(): ...
