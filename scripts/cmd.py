from subprocess import PIPE, Popen

def exec(command, printout = True):
    process = Popen(
        args=command,
        stdout=PIPE,
        shell=True
    )
    p = process.communicate()[0].decode()
    if printout:
        print(p)
    return p

def exist(command, var):
    return len([l for l in exec(command, False).splitlines() if l.endswith(var) or l.startswith(var)]) > 0