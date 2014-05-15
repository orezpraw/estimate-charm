#!/usr/bin/env python
#    Copyright 2013 Joshua Charles Campbell, Alex Wilson
#
#    This file is part of UnnaturalCode.
#    
#    UnnaturalCode is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    UnnaturalCode is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with UnnaturalCode.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import print_function

def main():
    import re
    import runpy
    import sys
    import traceback
    from copy import deepcopy
    import logging
    from logging import debug, info, warning, error
    #logging.getLogger().setLevel(logging.DEBUG)
    
    savedSysPath = deepcopy(sys.path)
    program = sys.argv[1]
    del sys.argv[1]
    
    source = open(program).read()
        
    # TODO: run this fn in a seperate proc using os.fork
    def runit():
      try:
          r = runpy.run_path(program)
      except SyntaxError as se:
          ei = sys.exc_info();
          traceback.print_exc();
          eip = (ei[0], str(ei[1]), traceback.extract_tb(ei[2]))
          try:
            eip[2].append(ei[1][1])
          except IndexError:
            eip[2].append((se.filename, se.lineno, None, None))
          return (eip)
      except Exception as e:
          ei = sys.exc_info();
          traceback.print_exc();
          eip = (ei[0], str(ei[1]), traceback.extract_tb(ei[2]))
          return (eip)
      return ((None, "None", [(program, None, None, None)]))
      
    e = runit()
    
    if e[0] == None:
      return
    
    sys.path = savedSysPath;
    
    from ucUser import pyUser
    ucpy = pyUser()
    
    worst = ucpy.sm.worstWindows(ucpy.lm(source))
    print("Suggest checking %s:%d:%d" % (program, worst[0][0][10][2][0], worst[0][0][10][2][1]), file=sys.stderr)
    print("Near:\n" + ucpy.lm(worst[0][0]).settle().deLex())
    
    ucpy.release()


if __name__ == '__main__':
    main()
