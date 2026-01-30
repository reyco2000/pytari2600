##########
pytari2600
##########
 
Python-based Atari 2600 emulator fork — with interactive debugger and fixed sound!
 
|license|
 
.. contents:: Table of Contents
   :depth: 2
   :local:
 
Overview
========
 
Atari 2600 emulator written in Python. The emulator is built from detailed
hardware documentation and supports multiple cartridge types, pluggable
graphics/audio backends, and a full-featured interactive debugger.
 
The emulator is written based on information from the following sources:
 
- `Atari 2600 TIA Hardware Notes <http://www.atarihq.com/danb/files/TIA_HW_Notes.txt>`_,
  by Andrew Towers
- *Stella Programmer's Guide*, by Steve Wright
- `Atari 2600 TIA Schematics <http://www.atariage.com/2600/archives/schematics_tia/index.html>`_
  (primarily used for the audio module)
- Sound fixes based on the `Stella emulator <https://github.com/stella-emu/stella>`_
 
Requirements
============
 
- **Python** 3.x
- **pygame** (1.9.1+)
- **numpy** *(optional)* — performance improvements
- **pyglet** *(optional)* — alternative graphics backend (not fully supported)
 
Installation
============
 
Create package:
 
.. code-block:: bash
 
   python setup.py sdist
 
Install:
 
.. code-block:: bash
 
   python setup.py install
 
Usage
=====
 
Show help:
 
.. code-block:: bash
 
   python -m pytari2600
 
.. code-block:: text
 
   usage: pytari2600.py [-h] [-d] [-r REPLAY_FILE] [-s STOP_CLOCK]
                        [-c {default,pb,mnet,cbs,e,fe,super,f4,single_bank}]
                        [-g {pyglet,pygame}] [--cpu {cpu,cpu_gen}]
                        [-a {oss_stretch,wav,oss,pygame,tia_dummy}] [-n]
                        cartridge_name
 
Command-Line Options
--------------------
 
.. list-table::
   :header-rows: 1
   :widths: 25 75
 
   * - Option
     - Description
   * - ``-c {type}``
     - Cartridge bank-switching type (``default``, ``pb``, ``mnet``, ``cbs``, ``e``, ``fe``, ``super``, ``f4``, ``single_bank``)
   * - ``-g {driver}``
     - Graphics backend (``pygame``, ``pyglet``)
   * - ``--cpu {impl}``
     - CPU implementation (``cpu``, ``cpu_gen``)
   * - ``-a {driver}``
     - Audio backend (``oss_stretch``, ``wav``, ``oss``, ``pygame``, ``tia_dummy``)
   * - ``-d``
     - Enable debug mode
   * - ``-r REPLAY_FILE``
     - Specify save/restore state file
   * - ``-s STOP_CLOCK``
     - Stop at a specific clock cycle
   * - ``-n``
     - No delay (fast emulation)
 
Examples
--------
 
Run a ROM (no audio by default, as audio can be unreliable):
 
.. code-block:: bash
 
   python -m pytari2600 myrom.bin
 
Specify a cartridge type:
 
.. code-block:: bash
 
   python -m pytari2600 -c cbs my_cbs_rom.bin
 
Save audio to a WAV file (for later listening):
 
.. code-block:: bash
 
   python -m pytari2600 -a wav my_cbs_rom.bin
 
Run with PyPy for better performance:
 
.. code-block:: bash
 
   pypy -m pytari2600 my_cbs_rom.bin
 
Controls
========
 
Emulation Keys
--------------
 
.. list-table::
   :header-rows: 1
   :widths: 20 80
 
   * - Key
     - Action
   * - Arrow keys
     - Move
   * - ``Z``
     - Fire button
   * - ``S``
     - Select
   * - ``R``
     - Reset
   * - ``1``
     - Difficulty switch (player 1)
   * - ``2``
     - Difficulty switch (player 2)
   * - ``[``
     - Save state (requires ``-r`` flag)
   * - ``]``
     - Restore state (requires ``-r`` flag)
   * - ``F12``
     - Toggle debugger (auto-pauses emulation)
   * - ``F11``
     - Single-step CPU instruction (while paused)
 
Debugger
========
 
Press ``F12`` during emulation to open the interactive debugger in a separate
window. The emulator automatically pauses when the debugger opens and resumes
when it is closed.
 
Views
-----
 
Press ``Tab`` to cycle through the available views:
 
Main
   CPU registers (A, X, Y, SP, PC, status flags) with change highlighting,
   plus a quick RAM overview.
 
Memory
   Full hex dump of RIOT RAM (``$0080``–``$00FF``), stack (``$0100``–``$01FF``),
   and ROM with an ASCII column.
 
Sprites
   Graphical display of Player 0/1 sprite shapes reconstructed from GRP
   writes, plus missile, ball, and playfield state.
 
TIA
   TIA register values and state.
 
ROM
   Full ROM viewer/editor with bank switching support.
 
Debugger Keys
-------------
 
.. list-table::
   :header-rows: 1
   :widths: 20 80
 
   * - Key
     - Action
   * - ``F12``
     - Close debugger (resumes emulation)
   * - ``F11``
     - Execute one CPU instruction (single-step)
   * - ``Tab``
     - Cycle through views
   * - ``P``
     - Toggle pause/resume
   * - ``D``
     - Dump full memory state to file
   * - ``Up`` / ``Down``
     - Scroll or move cursor
   * - ``PgUp`` / ``PgDn``
     - Scroll by page
   * - ``Home`` / ``End``
     - Jump to start/end
 
ROM Editor Keys
---------------
 
Available only in the ROM view:
 
.. list-table::
   :header-rows: 1
   :widths: 25 75
 
   * - Key
     - Action
   * - Arrow keys
     - Navigate cursor
   * - ``Enter``
     - Start editing byte at cursor
   * - ``0``–``9``, ``A``–``F``
     - Enter hex digits (high nibble first, low nibble commits)
   * - ``Escape``
     - Cancel edit
   * - ``B``
     - Cycle through ROM banks
 
Known Issues
============
 
- **FUTURE_PIXELS timing** — ``FUTURE_PIXELS`` is used to scan ahead of the
  current time, effectively delaying changes to graphics registers. The delays
  are register-specific, and since ROMs use the registers differently, the
  correct value varies. Generally, setting ``FUTURE_PIXELS`` between 1–9 will
  be fairly stable for a particular ROM, but it remains a workaround.
 
- **Performance** — On a standard machine, Python + pygame runs at roughly
  one-third of real-time. Using PyPy significantly improves speed.
 
TODO
====
 
- Speed improvements and profiling
- Cartridge auto-detection (determine bank-switching and RAM from ROM contents)
- More undocumented 6502 opcodes (added as encountered)
- Ensure the ``setup.py`` package hasn't introduced regressions
 
License
=======
 
This project is licensed under the MIT License. See the
`LICENSE <https://github.com/reyco2000/pytari2600/blob/master/LICENSE>`_ file
for details.
 
.. |license| image:: https://img.shields.io/badge/license-MIT-blue.svg
   :target: https://github.com/reyco2000/pytari2600/blob/master/LICENSE
   :alt: MIT License
