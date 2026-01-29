"""
Atari 2600 Debugger Module

Provides interactive debugging capabilities in a separate window:
- Memory viewer (full hex dump of all memory regions)
- CPU status viewer
- Sprite/TIA state viewer
- Memory dump to file

Press F12 to toggle debugger window on/off during emulation.
"""

import pygame
import os
from datetime import datetime

# Try to import pygame's SDL2 window support for separate window
try:
    from pygame._sdl2.video import Window, Renderer, Texture
    HAS_SDL2_WINDOW = True
except ImportError:
    HAS_SDL2_WINDOW = False


class DebuggerColors:
    """Color scheme for the debugger display"""
    BACKGROUND = (20, 20, 30)
    PANEL_BG = (30, 30, 45)
    BORDER = (80, 80, 100)
    TITLE = (255, 200, 100)
    TEXT = (200, 200, 200)
    HIGHLIGHT = (100, 255, 100)
    ADDRESS = (100, 180, 255)
    VALUE = (255, 255, 255)
    CHANGED = (255, 100, 100)
    SPRITE_P0 = (255, 100, 100)
    SPRITE_P1 = (100, 100, 255)
    SPRITE_M0 = (255, 200, 100)
    SPRITE_M1 = (100, 255, 200)
    SPRITE_BALL = (255, 255, 100)
    SPRITE_PF = (100, 255, 100)
    REGISTER_NAME = (180, 180, 255)
    FLAG_SET = (100, 255, 100)
    FLAG_CLEAR = (100, 100, 100)
    REGION_RAM = (100, 255, 100)
    REGION_ROM = (255, 200, 100)
    REGION_TIA = (255, 100, 255)
    REGION_RIOT = (100, 200, 255)


class Debugger:
    """
    Interactive debugger for the Atari 2600 emulator.
    Runs in a separate window from the main emulator.
    """

    # Window constants
    WINDOW_WIDTH = 1000
    WINDOW_HEIGHT = 800
    FONT_SIZE = 14
    SMALL_FONT_SIZE = 12
    LINE_HEIGHT = 16
    PANEL_PADDING = 10

    # Memory view constants
    BYTES_PER_LINE = 16

    # View modes
    VIEW_MAIN = 0      # Combined CPU + Memory overview
    VIEW_MEMORY = 1    # Full memory dump
    VIEW_SPRITES = 2   # Sprite/TIA graphics
    VIEW_TIA = 3       # TIA registers

    def __init__(self, atari):
        """Initialize the debugger."""
        self.atari = atari
        self.active = False
        self.paused = False
        self._step_requested = False
        self.view_mode = self.VIEW_MAIN

        # Memory viewer state
        self.memory_scroll = 0
        self.max_scroll = 0

        # Previous state for change detection
        self._prev_cpu_state = None
        self._prev_memory = None

        # Separate window components
        self._window = None
        self._renderer = None
        self._surface = None
        self._font = None
        self._small_font = None
        self._initialized = False

    def _init_display(self):
        """Initialize the separate debugger window"""
        if self._initialized:
            return True

        pygame.font.init()
        self._font = pygame.font.SysFont('Consolas', self.FONT_SIZE)
        self._small_font = pygame.font.SysFont('Consolas', self.SMALL_FONT_SIZE)

        if HAS_SDL2_WINDOW:
            try:
                # Create separate window using SDL2
                self._window = Window("Atari 2600 Debugger",
                                     size=(self.WINDOW_WIDTH, self.WINDOW_HEIGHT))
                self._window.show()
                self._renderer = Renderer(self._window)
                self._surface = pygame.Surface((self.WINDOW_WIDTH, self.WINDOW_HEIGHT))
                self._initialized = True
                return True
            except Exception as e:
                print(f"Failed to create SDL2 window: {e}")
                HAS_SDL2_WINDOW_RUNTIME = False

        # Fallback: use a surface that will be rendered as overlay
        self._surface = pygame.Surface((self.WINDOW_WIDTH, self.WINDOW_HEIGHT))
        self._initialized = True
        self._window = None
        return True

    def _close_window(self):
        """Close the debugger window"""
        if self._window:
            try:
                self._window.destroy()
            except:
                pass
            self._window = None
            self._renderer = None
        self._initialized = False

    def toggle(self):
        """Toggle debugger active state"""
        self.active = not self.active
        # Update input handler's debugger_active flag
        self.atari.inputs.debugger_active = self.active
        if self.active:
            if self._init_display():
                self.paused = True  # Auto-pause when debugger opens
                self._capture_state()
                print("Debugger activated - Emulation PAUSED")
                print("  F11: Step  F12: Close  Tab: Cycle views")
                print("  P: Pause/Resume  D: Dump to file")
                print("  Up/Down/PgUp/PgDn: Scroll memory view")
        else:
            self.paused = False  # Resume when debugger closes
            self._step_requested = False
            self._close_window()
            print("Debugger deactivated - Emulation RESUMED")

    def toggle_pause(self):
        """Toggle emulation pause state"""
        self.paused = not self.paused
        self._step_requested = False
        print(f"Emulation {'PAUSED' if self.paused else 'RESUMED'}")

    def step_one(self):
        """Request a single CPU step (used by F11)"""
        if self.paused:
            self._step_requested = True

    def consume_step(self):
        """Check and consume a pending step request. Returns True if a step should execute."""
        if self._step_requested:
            self._step_requested = False
            return True
        return False

    def _capture_state(self):
        """Capture current state for change detection"""
        pc_state = self.atari.pc_state
        self._prev_cpu_state = {
            'A': pc_state.A.value,
            'X': pc_state.X.value,
            'Y': pc_state.Y.value,
            'PC': pc_state.PC,
            'S': pc_state.S.value,
            'P': pc_state.P.value
        }
        self._prev_memory = list(self.atari.riot.ram)

    def handle_key(self, key):
        """Handle debugger keyboard input."""
        # F11 single step
        if key == pygame.K_F11:
            self.step_one()
            return
        # Tab cycles through views
        if key == pygame.K_TAB:
            self.view_mode = (self.view_mode + 1) % 4
            self.memory_scroll = 0
        elif key == pygame.K_p:
            self.toggle_pause()
        elif key == pygame.K_d:
            self.dump_memory()
        elif key == pygame.K_UP:
            self.memory_scroll = max(0, self.memory_scroll - 1)
        elif key == pygame.K_DOWN:
            self.memory_scroll = min(self.max_scroll, self.memory_scroll + 1)
        elif key == pygame.K_PAGEUP:
            self.memory_scroll = max(0, self.memory_scroll - 20)
        elif key == pygame.K_PAGEDOWN:
            self.memory_scroll = min(self.max_scroll, self.memory_scroll + 20)
        elif key == pygame.K_HOME:
            self.memory_scroll = 0
        elif key == pygame.K_END:
            self.memory_scroll = self.max_scroll

    def dump_memory(self):
        """Dump complete memory state to a file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"atari2600_dump_{timestamp}.txt"

        with open(filename, 'w') as f:
            f.write("=" * 70 + "\n")
            f.write(f"ATARI 2600 MEMORY DUMP - {datetime.now()}\n")
            f.write("=" * 70 + "\n\n")

            # CPU State
            pc_state = self.atari.pc_state
            f.write("CPU STATE\n")
            f.write("-" * 50 + "\n")
            f.write(f"PC:  ${pc_state.PC:04X}  (Program Counter)\n")
            f.write(f"A:   ${pc_state.A.value:02X}   ({pc_state.A.value:3d})  (Accumulator)\n")
            f.write(f"X:   ${pc_state.X.value:02X}   ({pc_state.X.value:3d})  (X Index)\n")
            f.write(f"Y:   ${pc_state.Y.value:02X}   ({pc_state.Y.value:3d})  (Y Index)\n")
            f.write(f"SP:  ${pc_state.S.value:02X}   (Stack Pointer -> ${0x100 + pc_state.S.value:04X})\n")
            f.write(f"P:   ${pc_state.P.value:02X}   ({pc_state.P.value:08b})  (Status)\n")
            f.write(f"     N={pc_state.P.get_N()} V={pc_state.P.get_V()} B={pc_state.P.get_B()} ")
            f.write(f"D={pc_state.P.get_D()} I={pc_state.P.get_I()} Z={pc_state.P.get_Z()} C={pc_state.P.get_C()}\n\n")

            # Timing
            f.write("TIMING\n")
            f.write("-" * 50 + "\n")
            f.write(f"System Clock: {self.atari.clocks.system_clock}\n")
            f.write(f"CPU Cycles:   {self.atari.clocks.system_clock // 3}\n\n")

            # RIOT RAM (128 bytes)
            f.write("RIOT RAM (128 bytes @ $0080-$00FF, mirrored at $0180-$01FF)\n")
            f.write("-" * 50 + "\n")
            ram = self.atari.riot.ram
            for i in range(0, 128, 16):
                addr = 0x80 + i
                hex_vals = ' '.join(f'{ram[i+j]:02X}' for j in range(16))
                ascii_vals = ''.join(chr(ram[i+j]) if 32 <= ram[i+j] < 127 else '.' for j in range(16))
                f.write(f"${addr:04X}: {hex_vals}  |{ascii_vals}|\n")
            f.write("\n")

            # Stack (part of RAM)
            sp = pc_state.S.value
            f.write(f"STACK (SP=${sp:02X}, Stack top at ${0x100+sp:04X})\n")
            f.write("-" * 50 + "\n")
            if sp < 0xFF:
                f.write("Stack contents (top to bottom):\n")
                for i in range(sp + 1, min(sp + 33, 0x100)):
                    val = ram[i & 0x7F]
                    f.write(f"  ${0x100+i:04X}: ${val:02X}\n")
            else:
                f.write("  (Stack empty)\n")
            f.write("\n")

            # TIA State
            stella = self.atari.stella
            f.write("TIA STATE\n")
            f.write("-" * 50 + "\n")
            f.write(f"Player 0:   GRP0=${stella.p0_state.p:02X} ({stella.p0_state.p:08b})\n")
            f.write(f"            RESP0={stella.p0_state.resp:3d}  NUSIZ0=${stella.p0_state.nusiz:02X}  REFP0=${stella.p0_state.refp:02X}\n")
            f.write(f"Player 1:   GRP1=${stella.p1_state.p:02X} ({stella.p1_state.p:08b})\n")
            f.write(f"            RESP1={stella.p1_state.resp:3d}  NUSIZ1=${stella.p1_state.nusiz:02X}  REFP1=${stella.p1_state.refp:02X}\n")
            f.write(f"Missile 0:  ENAM0=${stella.missile0.enam:02X}  RESM0={stella.missile0.resm:3d}\n")
            f.write(f"Missile 1:  ENAM1=${stella.missile1.enam:02X}  RESM1={stella.missile1.resm:3d}\n")
            f.write(f"Ball:       ENABL=${stella.ball.enabl:02X}  RESBL={stella.ball.resbl:3d}\n")
            f.write(f"Playfield:  PF0=${stella.playfield_state.pf0:02X}  PF1=${stella.playfield_state.pf1:02X}  PF2=${stella.playfield_state.pf2:02X}\n")
            f.write(f"            CTRLPF=${stella.playfield_state.ctrlpf:02X}\n\n")

            # Collisions
            coll = stella._collision_state
            f.write("COLLISION REGISTERS\n")
            f.write("-" * 50 + "\n")
            f.write(f"CXM0P:  ${coll._cxmp[0]:02X}  CXM1P:  ${coll._cxmp[1]:02X}\n")
            f.write(f"CXP0FB: ${coll._cxpfb[0]:02X}  CXP1FB: ${coll._cxpfb[1]:02X}\n")
            f.write(f"CXM0FB: ${coll._cxmfb[0]:02X}  CXM1FB: ${coll._cxmfb[1]:02X}\n")
            f.write(f"CXBLPF: ${coll._cxblpf:02X}  CXPPMM: ${coll._cxppmm:02X}\n\n")

            # ROM Cartridge
            f.write("ROM CARTRIDGE\n")
            f.write("-" * 50 + "\n")
            cart = self.atari.memory.cartridge
            if hasattr(cart, 'rom') and cart.rom:
                rom = cart.rom
                f.write(f"Size: {len(rom)} bytes ({len(rom)//1024}KB)\n\n")

                # Full ROM dump
                for i in range(0, len(rom), 16):
                    addr = 0x1000 + i
                    end = min(i + 16, len(rom))
                    hex_vals = ' '.join(f'{rom[i+j]:02X}' for j in range(end - i))
                    ascii_vals = ''.join(chr(rom[i+j]) if 32 <= rom[i+j] < 127 else '.' for j in range(end - i))
                    f.write(f"${addr:04X}: {hex_vals:<48}  |{ascii_vals}|\n")

                # Reset/IRQ vectors
                if len(rom) >= 4:
                    f.write(f"\nVectors:\n")
                    if len(rom) >= 0xFFE:
                        nmi = (rom[0xFFB] << 8) | rom[0xFFA] if len(rom) > 0xFFB else 0
                        reset = (rom[0xFFD] << 8) | rom[0xFFC]
                        irq = (rom[0xFFF] << 8) | rom[0xFFE]
                        f.write(f"  NMI:   ${nmi:04X}\n")
                        f.write(f"  RESET: ${reset:04X}\n")
                        f.write(f"  IRQ:   ${irq:04X}\n")

        print(f"Memory dumped to: {filename}")
        return filename

    def render(self, screen=None):
        """Render the debugger to its window or overlay."""
        if not self.active or not self._initialized:
            return

        self._surface.fill(DebuggerColors.BACKGROUND)

        # Draw title bar
        self._draw_title_bar()

        # Draw based on view mode
        if self.view_mode == self.VIEW_MAIN:
            self._draw_main_view()
        elif self.view_mode == self.VIEW_MEMORY:
            self._draw_full_memory_view()
        elif self.view_mode == self.VIEW_SPRITES:
            self._draw_sprite_view()
        elif self.view_mode == self.VIEW_TIA:
            self._draw_tia_view()

        # Draw help bar
        self._draw_help_bar()

        # Update the window
        if self._window and self._renderer:
            try:
                texture = Texture.from_surface(self._renderer, self._surface)
                self._renderer.clear()
                texture.draw()
                self._renderer.present()
            except Exception as e:
                # Fallback to overlay mode
                if screen:
                    x = (screen.get_width() - self.WINDOW_WIDTH) // 2
                    y = (screen.get_height() - self.WINDOW_HEIGHT) // 2
                    screen.blit(self._surface, (max(0, x), max(0, y)))
        elif screen:
            # Overlay mode fallback
            x = (screen.get_width() - self.WINDOW_WIDTH) // 2
            y = (screen.get_height() - self.WINDOW_HEIGHT) // 2
            screen.blit(self._surface, (max(0, x), max(0, y)))

    def _draw_title_bar(self):
        """Draw the title bar"""
        pygame.draw.rect(self._surface, DebuggerColors.PANEL_BG,
                        (0, 0, self.WINDOW_WIDTH, 30))
        pygame.draw.line(self._surface, DebuggerColors.BORDER,
                        (0, 30), (self.WINDOW_WIDTH, 30), 2)

        title = "ATARI 2600 DEBUGGER"
        if self.paused:
            title += "  [PAUSED]"
        title_surf = self._font.render(title, True, DebuggerColors.TITLE)
        self._surface.blit(title_surf, (self.PANEL_PADDING, 6))

        # View tabs - Tab key cycles through
        modes = ["Main", "Memory", "Sprites", "TIA"]
        tab_x = 350
        for i, mode in enumerate(modes):
            if i == self.view_mode:
                # Highlight current view
                pygame.draw.rect(self._surface, DebuggerColors.HIGHLIGHT,
                               (tab_x - 5, 2, len(mode) * 10 + 10, 26), 0, 3)
                tab_surf = self._font.render(mode, True, DebuggerColors.BACKGROUND)
            else:
                tab_surf = self._font.render(mode, True, DebuggerColors.TEXT)
            self._surface.blit(tab_surf, (tab_x, 6))
            tab_x += 100

    def _draw_help_bar(self):
        """Draw help bar at bottom"""
        y = self.WINDOW_HEIGHT - 25
        pygame.draw.rect(self._surface, DebuggerColors.PANEL_BG,
                        (0, y, self.WINDOW_WIDTH, 25))
        pygame.draw.line(self._surface, DebuggerColors.BORDER,
                        (0, y), (self.WINDOW_WIDTH, y), 1)

        help_text = "F11:Step  Tab:Cycle Views  P:Pause/Resume  D:Dump  Arrows:Scroll  F12:Close"
        help_surf = self._small_font.render(help_text, True, DebuggerColors.TEXT)
        self._surface.blit(help_surf, (self.PANEL_PADDING, y + 5))

    def _draw_main_view(self):
        """Draw combined CPU and memory overview"""
        # Left panel: CPU State
        self._draw_cpu_panel(10, 40, 480, 350)

        # Right panel: Quick memory view
        self._draw_quick_memory_panel(500, 40, 490, 350)

        # Bottom panel: TIA overview
        self._draw_tia_overview_panel(10, 400, 980, 370)

    def _draw_cpu_panel(self, x, y, w, h):
        """Draw CPU state panel"""
        pygame.draw.rect(self._surface, DebuggerColors.PANEL_BG, (x, y, w, h))
        pygame.draw.rect(self._surface, DebuggerColors.BORDER, (x, y, w, h), 1)

        pc_state = self.atari.pc_state
        py = y + 10

        title = self._font.render("CPU STATE", True, DebuggerColors.TITLE)
        self._surface.blit(title, (x + 10, py))
        py += 30

        # Registers
        regs = [
            ("PC", f"${pc_state.PC:04X}", f"Program Counter"),
            ("A", f"${pc_state.A.value:02X}", f"= {pc_state.A.value:3d} = {pc_state.A.value:08b}"),
            ("X", f"${pc_state.X.value:02X}", f"= {pc_state.X.value:3d} = {pc_state.X.value:08b}"),
            ("Y", f"${pc_state.Y.value:02X}", f"= {pc_state.Y.value:3d} = {pc_state.Y.value:08b}"),
            ("SP", f"${pc_state.S.value:02X}", f"-> Stack at ${0x100 + pc_state.S.value:04X}"),
        ]

        for name, val, extra in regs:
            changed = self._is_changed(name if name != 'SP' else 'S',
                                       pc_state.PC if name == 'PC' else getattr(pc_state, name if name != 'SP' else 'S').value)

            name_surf = self._font.render(f"{name}:", True, DebuggerColors.REGISTER_NAME)
            self._surface.blit(name_surf, (x + 20, py))

            color = DebuggerColors.CHANGED if changed else DebuggerColors.VALUE
            val_surf = self._font.render(val, True, color)
            self._surface.blit(val_surf, (x + 60, py))

            extra_surf = self._small_font.render(extra, True, DebuggerColors.TEXT)
            self._surface.blit(extra_surf, (x + 130, py))
            py += 22

        # Status flags
        py += 10
        title = self._font.render("STATUS FLAGS", True, DebuggerColors.TITLE)
        self._surface.blit(title, (x + 10, py))
        py += 25

        flags = [
            ('N', 'Negative', pc_state.P.get_N()),
            ('V', 'Overflow', pc_state.P.get_V()),
            ('B', 'Break', pc_state.P.get_B()),
            ('D', 'Decimal', pc_state.P.get_D()),
            ('I', 'IRQ Dis', pc_state.P.get_I()),
            ('Z', 'Zero', pc_state.P.get_Z()),
            ('C', 'Carry', pc_state.P.get_C()),
        ]

        fx = x + 20
        for flag, name, val in flags:
            color = DebuggerColors.FLAG_SET if val else DebuggerColors.FLAG_CLEAR
            text = f"{flag}:{val}"
            surf = self._font.render(text, True, color)
            self._surface.blit(surf, (fx, py))
            fx += 60

        py += 25
        p_val = pc_state.P.value
        p_surf = self._small_font.render(f"P = ${p_val:02X} = {p_val:08b}", True, DebuggerColors.TEXT)
        self._surface.blit(p_surf, (x + 20, py))

        # Timing
        py += 30
        title = self._font.render("TIMING", True, DebuggerColors.TITLE)
        self._surface.blit(title, (x + 10, py))
        py += 25

        clk = self.atari.clocks.system_clock
        stella = self.atari.stella
        scan_clk = clk - stella._screen_start_clock
        scanline = scan_clk // stella.HORIZONTAL_TICKS
        hpos = scan_clk % stella.HORIZONTAL_TICKS

        timing = [
            f"Clock: {clk}  CPU Cycles: {clk // 3}",
            f"Scanline: {scanline}  H-Pos: {hpos}",
        ]
        for t in timing:
            surf = self._small_font.render(t, True, DebuggerColors.TEXT)
            self._surface.blit(surf, (x + 20, py))
            py += 18

    def _draw_quick_memory_panel(self, x, y, w, h):
        """Draw quick RAM overview"""
        pygame.draw.rect(self._surface, DebuggerColors.PANEL_BG, (x, y, w, h))
        pygame.draw.rect(self._surface, DebuggerColors.BORDER, (x, y, w, h), 1)

        py = y + 10
        title = self._font.render("RAM (128 bytes @ $0080-$00FF)", True, DebuggerColors.REGION_RAM)
        self._surface.blit(title, (x + 10, py))
        py += 25

        # Header
        header = "Addr  " + " ".join(f"{i:02X}" for i in range(16)) + "  ASCII"
        header_surf = self._small_font.render(header, True, DebuggerColors.ADDRESS)
        self._surface.blit(header_surf, (x + 10, py))
        py += 18

        ram = self.atari.riot.ram
        for row in range(8):  # Show all 128 bytes (8 rows of 16)
            offset = row * 16
            addr = 0x80 + offset

            # Address
            addr_surf = self._small_font.render(f"${addr:04X}", True, DebuggerColors.ADDRESS)
            self._surface.blit(addr_surf, (x + 10, py))

            # Hex values
            hx = x + 60
            ascii_str = ""
            for i in range(16):
                val = ram[offset + i]
                changed = self._prev_memory and offset + i < len(self._prev_memory) and self._prev_memory[offset + i] != val
                color = DebuggerColors.CHANGED if changed else DebuggerColors.VALUE
                hex_surf = self._small_font.render(f"{val:02X}", True, color)
                self._surface.blit(hex_surf, (hx, py))
                hx += 21
                ascii_str += chr(val) if 32 <= val < 127 else '.'

            # ASCII
            ascii_surf = self._small_font.render(ascii_str, True, DebuggerColors.TEXT)
            self._surface.blit(ascii_surf, (hx + 10, py))
            py += 16

        # Stack pointer indicator
        py += 10
        sp = self.atari.pc_state.S.value
        sp_text = f"Stack Pointer: ${sp:02X} (Stack at ${0x100 + sp:04X})"
        sp_surf = self._small_font.render(sp_text, True, DebuggerColors.HIGHLIGHT)
        self._surface.blit(sp_surf, (x + 10, py))

    def _draw_tia_overview_panel(self, x, y, w, h):
        """Draw TIA overview panel"""
        pygame.draw.rect(self._surface, DebuggerColors.PANEL_BG, (x, y, w, h))
        pygame.draw.rect(self._surface, DebuggerColors.BORDER, (x, y, w, h), 1)

        stella = self.atari.stella
        py = y + 10

        title = self._font.render("TIA / GRAPHICS STATE", True, DebuggerColors.TITLE)
        self._surface.blit(title, (x + 10, py))
        py += 25

        # Players
        col1_x = x + 10
        col2_x = x + 340
        col3_x = x + 670

        # Player 0
        p0_text = f"P0: GRP=${stella.p0_state.p:02X} ({stella.p0_state.p:08b}) RESP={stella.p0_state.resp:3d}"
        p0_surf = self._small_font.render(p0_text, True, DebuggerColors.SPRITE_P0)
        self._surface.blit(p0_surf, (col1_x, py))

        # Player 1
        p1_text = f"P1: GRP=${stella.p1_state.p:02X} ({stella.p1_state.p:08b}) RESP={stella.p1_state.resp:3d}"
        p1_surf = self._small_font.render(p1_text, True, DebuggerColors.SPRITE_P1)
        self._surface.blit(p1_surf, (col2_x, py))
        py += 20

        # Missiles
        m0_text = f"M0: ENAM=${stella.missile0.enam:02X} RESM={stella.missile0.resm:3d}"
        m0_surf = self._small_font.render(m0_text, True, DebuggerColors.SPRITE_M0)
        self._surface.blit(m0_surf, (col1_x, py))

        m1_text = f"M1: ENAM=${stella.missile1.enam:02X} RESM={stella.missile1.resm:3d}"
        m1_surf = self._small_font.render(m1_text, True, DebuggerColors.SPRITE_M1)
        self._surface.blit(m1_surf, (col2_x, py))

        # Ball
        bl_text = f"BL: ENABL=${stella.ball.enabl:02X} RESBL={stella.ball.resbl:3d}"
        bl_surf = self._small_font.render(bl_text, True, DebuggerColors.SPRITE_BALL)
        self._surface.blit(bl_surf, (col3_x, py))
        py += 20

        # Playfield
        pf = stella.playfield_state
        pf_text = f"PF: PF0=${pf.pf0:02X} PF1=${pf.pf1:02X} PF2=${pf.pf2:02X}  CTRLPF=${pf.ctrlpf:02X}"
        pf_surf = self._small_font.render(pf_text, True, DebuggerColors.SPRITE_PF)
        self._surface.blit(pf_surf, (col1_x, py))
        py += 25

        # Scanline visualization
        title = self._small_font.render("Scanline Preview:", True, DebuggerColors.TITLE)
        self._surface.blit(title, (col1_x, py))
        py += 18

        self._draw_scanline_preview(col1_x, py, 960)
        py += 30

        # Input state
        inputs = self.atari.inputs
        joy = []
        if not (inputs.swcha & 0x10): joy.append("UP")
        if not (inputs.swcha & 0x20): joy.append("DOWN")
        if not (inputs.swcha & 0x40): joy.append("LEFT")
        if not (inputs.swcha & 0x80): joy.append("RIGHT")
        if not (inputs.input7 & 0x80): joy.append("FIRE")

        input_text = f"Input: SWCHA=${inputs.swcha:02X} SWCHB=${inputs.swchb:02X}  [{', '.join(joy) if joy else 'none'}]"
        input_surf = self._small_font.render(input_text, True, DebuggerColors.TEXT)
        self._surface.blit(input_surf, (col1_x, py))

    def _draw_scanline_preview(self, x, y, width):
        """Draw a visual representation of the current scanline"""
        stella = self.atari.stella
        scale = width // 160

        # Get scan data
        p0 = stella.p0_state.get_player_scan()
        p1 = stella.p1_state.get_player_scan()
        m0 = stella.missile0.get_missile_scan()
        m1 = stella.missile1.get_missile_scan()
        bl = stella.ball.get_ball_scan()
        pf = stella.playfield_state.get_playfield_scan()

        # Background
        pygame.draw.rect(self._surface, (40, 40, 50), (x, y, width, 16))

        # Draw each pixel
        for i in range(160):
            px = x + i * scale
            if i < len(pf) and pf[i]:
                pygame.draw.rect(self._surface, DebuggerColors.SPRITE_PF, (px, y, scale-1, 16))
            if i < len(bl) and bl[i]:
                pygame.draw.rect(self._surface, DebuggerColors.SPRITE_BALL, (px, y+2, scale-1, 12))
            if i < len(m1) and m1[i]:
                pygame.draw.rect(self._surface, DebuggerColors.SPRITE_M1, (px, y+4, scale-1, 8))
            if i < len(m0) and m0[i]:
                pygame.draw.rect(self._surface, DebuggerColors.SPRITE_M0, (px, y+4, scale-1, 8))
            if i < len(p1) and p1[i]:
                pygame.draw.rect(self._surface, DebuggerColors.SPRITE_P1, (px, y+6, scale-1, 4))
            if i < len(p0) and p0[i]:
                pygame.draw.rect(self._surface, DebuggerColors.SPRITE_P0, (px, y+6, scale-1, 4))

    def _draw_full_memory_view(self):
        """Draw full memory dump view"""
        y = 40

        # Calculate how many lines we can display
        available_height = self.WINDOW_HEIGHT - 80  # Title + help bar
        lines_per_page = available_height // self.LINE_HEIGHT

        # Build complete memory map
        memory_lines = []

        # RAM (128 bytes)
        memory_lines.append(("header", "RIOT RAM (128 bytes @ $0080-$00FF)", DebuggerColors.REGION_RAM))
        ram = self.atari.riot.ram
        for i in range(0, 128, 16):
            addr = 0x80 + i
            hex_vals = ' '.join(f'{ram[i+j]:02X}' for j in range(16))
            ascii_vals = ''.join(chr(ram[i+j]) if 32 <= ram[i+j] < 127 else '.' for j in range(16))
            memory_lines.append(("data", addr, [ram[i+j] for j in range(16)], ascii_vals, "ram", i))

        memory_lines.append(("spacer", ""))

        # Stack view
        sp = self.atari.pc_state.S.value
        memory_lines.append(("header", f"STACK (SP=${sp:02X}, addresses $0100-$01FF)", DebuggerColors.REGION_RAM))
        for i in range(0, 128, 16):
            addr = 0x100 + i
            hex_vals = ' '.join(f'{ram[i+j]:02X}' for j in range(16))
            ascii_vals = ''.join(chr(ram[i+j]) if 32 <= ram[i+j] < 127 else '.' for j in range(16))
            # Mark stack pointer position
            is_stack_line = (sp >= i) and (sp < i + 16)
            memory_lines.append(("stack", addr, [ram[i+j] for j in range(16)], ascii_vals, sp if is_stack_line else -1))

        memory_lines.append(("spacer", ""))

        # ROM
        cart = self.atari.memory.cartridge
        if hasattr(cart, 'rom') and cart.rom:
            rom = cart.rom
            memory_lines.append(("header", f"ROM CARTRIDGE ({len(rom)} bytes @ $1000-${0x1000+len(rom)-1:04X})", DebuggerColors.REGION_ROM))
            for i in range(0, len(rom), 16):
                addr = 0x1000 + i
                end = min(i + 16, len(rom))
                vals = [rom[i+j] if i+j < len(rom) else 0 for j in range(16)]
                hex_vals = ' '.join(f'{v:02X}' for v in vals[:end-i])
                ascii_vals = ''.join(chr(v) if 32 <= v < 127 else '.' for v in vals[:end-i])
                memory_lines.append(("rom", addr, vals[:end-i], ascii_vals))

        # Update max scroll
        self.max_scroll = max(0, len(memory_lines) - lines_per_page + 5)

        # Draw header
        header = "Address   " + " ".join(f"{i:02X}" for i in range(16)) + "   ASCII"
        header_surf = self._small_font.render(header, True, DebuggerColors.ADDRESS)
        self._surface.blit(header_surf, (10, y))
        y += 20

        # Draw visible lines
        start_line = self.memory_scroll
        for idx in range(start_line, min(start_line + lines_per_page, len(memory_lines))):
            line = memory_lines[idx]

            if line[0] == "header":
                surf = self._font.render(line[1], True, line[2])
                self._surface.blit(surf, (10, y))
            elif line[0] == "spacer":
                pass  # Just skip a line
            elif line[0] == "data":
                _, addr, vals, ascii_str, region, offset = line
                # Address
                addr_surf = self._small_font.render(f"${addr:04X}:", True, DebuggerColors.ADDRESS)
                self._surface.blit(addr_surf, (10, y))
                # Values
                hx = 70
                for i, val in enumerate(vals):
                    changed = self._prev_memory and offset + i < len(self._prev_memory) and self._prev_memory[offset + i] != val
                    color = DebuggerColors.CHANGED if changed else DebuggerColors.VALUE
                    hex_surf = self._small_font.render(f"{val:02X}", True, color)
                    self._surface.blit(hex_surf, (hx, y))
                    hx += 21
                # ASCII
                ascii_surf = self._small_font.render(f"  {ascii_str}", True, DebuggerColors.TEXT)
                self._surface.blit(ascii_surf, (hx, y))
            elif line[0] == "stack":
                _, addr, vals, ascii_str, sp_pos = line
                addr_surf = self._small_font.render(f"${addr:04X}:", True, DebuggerColors.ADDRESS)
                self._surface.blit(addr_surf, (10, y))
                hx = 70
                for i, val in enumerate(vals):
                    # Highlight stack pointer position
                    if sp_pos >= 0 and (addr - 0x100 + i) == sp_pos:
                        color = DebuggerColors.HIGHLIGHT
                    else:
                        color = DebuggerColors.VALUE
                    hex_surf = self._small_font.render(f"{val:02X}", True, color)
                    self._surface.blit(hex_surf, (hx, y))
                    hx += 21
                ascii_surf = self._small_font.render(f"  {ascii_str}", True, DebuggerColors.TEXT)
                self._surface.blit(ascii_surf, (hx, y))
            elif line[0] == "rom":
                _, addr, vals, ascii_str = line
                addr_surf = self._small_font.render(f"${addr:04X}:", True, DebuggerColors.ADDRESS)
                self._surface.blit(addr_surf, (10, y))
                hx = 70
                for val in vals:
                    hex_surf = self._small_font.render(f"{val:02X}", True, DebuggerColors.VALUE)
                    self._surface.blit(hex_surf, (hx, y))
                    hx += 21
                ascii_surf = self._small_font.render(f"  {ascii_str}", True, DebuggerColors.TEXT)
                self._surface.blit(ascii_surf, (hx, y))

            y += self.LINE_HEIGHT

        # Scroll indicator
        total = len(memory_lines)
        visible = min(lines_per_page, total)
        pct = (self.memory_scroll / max(1, self.max_scroll)) * 100 if self.max_scroll > 0 else 0
        scroll_text = f"Lines {self.memory_scroll+1}-{self.memory_scroll+visible} of {total}  ({pct:.0f}%)"
        scroll_surf = self._small_font.render(scroll_text, True, DebuggerColors.TEXT)
        self._surface.blit(scroll_surf, (self.WINDOW_WIDTH - 250, 40))

    def _draw_sprite_view(self):
        """Draw detailed sprite view with graphical representations"""
        stella = self.atari.stella
        y = 45

        # Title
        title = self._font.render("SPRITE GRAPHICS VIEWER", True, DebuggerColors.TITLE)
        self._surface.blit(title, (10, y))
        y += 30

        # Large graphical display of all sprites
        self._draw_sprite_graphics_panel(10, y, 980, 300, stella)
        y += 310

        # Sprite info panels in a row
        # Player 0
        self._draw_player_info_panel("P0", stella.p0_state, DebuggerColors.SPRITE_P0, 10, y, 240, 150)
        # Player 1
        self._draw_player_info_panel("P1", stella.p1_state, DebuggerColors.SPRITE_P1, 260, y, 240, 150)
        # Missiles & Ball
        self._draw_missiles_ball_info_panel(stella, 510, y, 240, 150)
        # Playfield
        self._draw_playfield_info_panel(stella.playfield_state, 760, y, 230, 150)
        y += 160

        # Full scanline preview
        title = self._font.render("COMPOSITE SCANLINE (all objects)", True, DebuggerColors.TITLE)
        self._surface.blit(title, (10, y))
        y += 20
        self._draw_scanline_preview(10, y, 980)

    def _draw_sprite_graphics_panel(self, x, y, w, h, stella):
        """Draw large graphical representations of all sprites captured this frame"""
        pygame.draw.rect(self._surface, DebuggerColors.PANEL_BG, (x, y, w, h))
        pygame.draw.rect(self._surface, DebuggerColors.BORDER, (x, y, w, h), 1)

        scale = 5
        sprite_h = 8 * scale  # Height of each sprite graphic

        # --- Player 0: show all unique GRP patterns from this frame ---
        px = x + 15
        py = y + 10
        label = self._font.render("PLAYER 0 (frame patterns)", True, DebuggerColors.SPRITE_P0)
        self._surface.blit(label, (px, py))
        py += 22

        p0_history = getattr(stella.p0_state, '_debug_grp_display', [])
        if p0_history:
            gx = px
            for grp in p0_history[:10]:  # Show up to 10 patterns
                self._draw_sprite_tile(gx, py, grp, DebuggerColors.SPRITE_P0, scale,
                                       stella.p0_state.refp & 0x8)
                gx += 8 * scale + 12
                if gx > x + w // 2 - 20:
                    break
        else:
            empty = self._small_font.render("(no sprite data this frame)", True, DebuggerColors.FLAG_CLEAR)
            self._surface.blit(empty, (px, py))

        # --- Player 1: show all unique GRP patterns from this frame ---
        px = x + w // 2 + 10
        py = y + 10
        label = self._font.render("PLAYER 1 (frame patterns)", True, DebuggerColors.SPRITE_P1)
        self._surface.blit(label, (px, py))
        py += 22

        p1_history = getattr(stella.p1_state, '_debug_grp_display', [])
        if p1_history:
            gx = px
            for grp in p1_history[:10]:
                self._draw_sprite_tile(gx, py, grp, DebuggerColors.SPRITE_P1, scale,
                                       stella.p1_state.refp & 0x8)
                gx += 8 * scale + 12
                if gx > x + w - 20:
                    break
        else:
            empty = self._small_font.render("(no sprite data this frame)", True, DebuggerColors.FLAG_CLEAR)
            self._surface.blit(empty, (px, py))

        # --- Missiles & Ball ---
        row2_y = y + 40 + sprite_h + 50
        px = x + 15
        label = self._font.render("MISSILES", True, DebuggerColors.SPRITE_M0)
        self._surface.blit(label, (px, row2_y))
        self._draw_missile_graphic(px, row2_y + 20, stella.missile0, DebuggerColors.SPRITE_M0, "M0")
        self._draw_missile_graphic(px + 80, row2_y + 20, stella.missile1, DebuggerColors.SPRITE_M1, "M1")

        px = x + 250
        label = self._font.render("BALL", True, DebuggerColors.SPRITE_BALL)
        self._surface.blit(label, (px, row2_y))
        self._draw_ball_graphic(px, row2_y + 20, stella.ball, DebuggerColors.SPRITE_BALL)

        # --- Playfield pattern ---
        pf_y = row2_y
        px = x + 420
        label = self._font.render("PLAYFIELD PATTERN", True, DebuggerColors.SPRITE_PF)
        self._surface.blit(label, (px, pf_y))
        pf_y += 22
        self._draw_playfield_graphic(px, pf_y, stella.playfield_state, w - 430)

    def _draw_sprite_tile(self, x, y, grp, color, scale, reflect):
        """Draw one 8-bit sprite pattern as a tile with hex label"""
        width = 8 * scale
        height = 8 * scale

        # Background
        pygame.draw.rect(self._surface, (40, 40, 50), (x, y, width, height))
        pygame.draw.rect(self._surface, DebuggerColors.BORDER, (x, y, width, height), 1)

        # Draw each bit as a pixel block
        for i in range(8):
            bit_idx = i if reflect else (7 - i)
            if (grp >> bit_idx) & 1:
                pygame.draw.rect(self._surface, color,
                               (x + i * scale, y, scale - 1, height))

        # Hex label below
        hex_surf = self._small_font.render(f"${grp:02X}", True, color)
        self._surface.blit(hex_surf, (x, y + height + 2))

    def _draw_large_sprite_graphic(self, x, y, grp, color, scale, reflect, nusiz):
        """Draw a large representation of an 8-bit player graphic"""
        # Draw border/background
        width = 8 * scale
        height = 16 * scale  # Make it tall like actual sprites
        pygame.draw.rect(self._surface, (40, 40, 50), (x, y, width, height))
        pygame.draw.rect(self._surface, DebuggerColors.BORDER, (x, y, width, height), 1)

        # Draw the 8-bit pattern
        for i in range(8):
            bit_idx = i if reflect else (7 - i)
            if (grp >> bit_idx) & 1:
                pygame.draw.rect(self._surface, color,
                               (x + i * scale, y, scale - 1, height))

        # Show hex value below
        hex_text = f"${grp:02X}"
        hex_surf = self._small_font.render(hex_text, True, color)
        self._surface.blit(hex_surf, (x, y + height + 5))

        # Show binary pattern
        bin_text = f"{grp:08b}"
        bin_surf = self._small_font.render(bin_text, True, DebuggerColors.TEXT)
        self._surface.blit(bin_surf, (x, y + height + 20))

        # Show NUSIZ info
        num, size, gap = self._decode_nusiz(nusiz)
        nusiz_text = f"x{num} sz{size}"
        nusiz_surf = self._small_font.render(nusiz_text, True, DebuggerColors.TEXT)
        self._surface.blit(nusiz_surf, (x, y + height + 35))

    def _decode_nusiz(self, nusiz):
        """Decode NUSIZ register to number, size, gap"""
        val = nusiz & 0x7
        if val == 0: return (1, 1, 0)
        elif val == 1: return (2, 1, 2)
        elif val == 2: return (2, 1, 4)
        elif val == 3: return (3, 1, 2)
        elif val == 4: return (2, 1, 8)
        elif val == 5: return (1, 2, 0)
        elif val == 6: return (3, 1, 4)
        elif val == 7: return (1, 4, 0)
        return (1, 1, 0)

    def _draw_missile_graphic(self, x, y, missile, color, label):
        """Draw missile graphic representation"""
        # Draw label
        lbl_surf = self._small_font.render(label, True, color)
        self._surface.blit(lbl_surf, (x, y))

        # Draw missile representation
        my = y + 20
        enabled = missile.enam & 0x02
        width = 1 << ((missile.nusiz & 0x30) >> 4)
        scale = 8

        # Background
        pygame.draw.rect(self._surface, (40, 40, 50), (x, my, 60, 80))
        pygame.draw.rect(self._surface, DebuggerColors.BORDER, (x, my, 60, 80), 1)

        if enabled:
            # Draw missile as a vertical bar
            mw = width * scale
            pygame.draw.rect(self._surface, color, (x + 20, my + 10, mw, 60))

        # Status text
        status = "ON" if enabled else "OFF"
        status_surf = self._small_font.render(status, True,
                                             DebuggerColors.HIGHLIGHT if enabled else DebuggerColors.FLAG_CLEAR)
        self._surface.blit(status_surf, (x + 5, my + 65))

    def _draw_ball_graphic(self, x, y, ball, color):
        """Draw ball graphic representation"""
        # Draw ball representation
        enabled = ball.enabl & 0x02
        width = 1 << ((ball.ctrlpf & 0x30) >> 4)
        scale = 8

        # Background
        pygame.draw.rect(self._surface, (40, 40, 50), (x, y, 80, 100))
        pygame.draw.rect(self._surface, DebuggerColors.BORDER, (x, y, 80, 100), 1)

        if enabled:
            # Draw ball as a square
            bw = width * scale
            pygame.draw.rect(self._surface, color, (x + 30 - bw//2, y + 30, bw, bw))

        # Status text
        status = "ON" if enabled else "OFF"
        status_surf = self._small_font.render(status, True,
                                             DebuggerColors.HIGHLIGHT if enabled else DebuggerColors.FLAG_CLEAR)
        self._surface.blit(status_surf, (x + 5, y + 80))

        # Width info
        w_text = f"W:{width}px"
        w_surf = self._small_font.render(w_text, True, DebuggerColors.TEXT)
        self._surface.blit(w_surf, (x + 40, y + 80))

    def _draw_playfield_graphic(self, x, y, pf, width):
        """Draw playfield pattern visualization"""
        pf_scan = pf.get_playfield_scan()
        scale = width // 160

        # Background
        pygame.draw.rect(self._surface, (40, 40, 50), (x, y, width, 24))
        pygame.draw.rect(self._surface, DebuggerColors.BORDER, (x, y, width, 24), 1)

        # Draw each pixel
        for i in range(160):
            if i < len(pf_scan) and pf_scan[i]:
                pygame.draw.rect(self._surface, DebuggerColors.SPRITE_PF,
                               (x + i * scale, y + 2, scale - 1, 20))

        # Show PF register values below
        pf_text = f"PF0=${pf.pf0:02X}  PF1=${pf.pf1:02X}  PF2=${pf.pf2:02X}  CTRLPF=${pf.ctrlpf:02X}"
        pf_surf = self._small_font.render(pf_text, True, DebuggerColors.TEXT)
        self._surface.blit(pf_surf, (x, y + 28))

    def _draw_player_info_panel(self, name, player, color, x, y, w, h):
        """Draw compact player info panel"""
        pygame.draw.rect(self._surface, DebuggerColors.PANEL_BG, (x, y, w, h))
        pygame.draw.rect(self._surface, color, (x, y, w, h), 2)

        py = y + 8
        title = self._font.render(name, True, color)
        self._surface.blit(title, (x + 10, py))
        py += 22

        history = getattr(player, '_debug_grp_display', [])
        n_patterns = len(history)

        info = [
            f"Patterns: {n_patterns}",
            f"RESP: {player.resp:3d}",
            f"NUSIZ: ${player.nusiz:02X}",
            f"REFP: {'Yes' if player.refp & 0x8 else 'No'}",
            f"VDELP: ${player.vdelp:02X}",
        ]

        for line in info:
            surf = self._small_font.render(line, True, DebuggerColors.TEXT)
            self._surface.blit(surf, (x + 10, py))
            py += 16

    def _draw_missiles_ball_info_panel(self, stella, x, y, w, h):
        """Draw missiles and ball info panel"""
        pygame.draw.rect(self._surface, DebuggerColors.PANEL_BG, (x, y, w, h))
        pygame.draw.rect(self._surface, DebuggerColors.BORDER, (x, y, w, h), 1)

        py = y + 8
        title = self._font.render("M0/M1/BL", True, DebuggerColors.TITLE)
        self._surface.blit(title, (x + 10, py))
        py += 22

        m0 = stella.missile0
        m1 = stella.missile1
        bl = stella.ball

        info = [
            f"M0: {'ON' if m0.enam & 0x02 else 'off'} @{m0.resm:3d}",
            f"M1: {'ON' if m1.enam & 0x02 else 'off'} @{m1.resm:3d}",
            f"BL: {'ON' if bl.enabl & 0x02 else 'off'} @{bl.resbl:3d}",
            f"Ball W: {1 << ((bl.ctrlpf & 0x30) >> 4)}px",
        ]

        colors = [DebuggerColors.SPRITE_M0, DebuggerColors.SPRITE_M1,
                 DebuggerColors.SPRITE_BALL, DebuggerColors.TEXT]

        for i, line in enumerate(info):
            surf = self._small_font.render(line, True, colors[i])
            self._surface.blit(surf, (x + 10, py))
            py += 18

    def _draw_playfield_info_panel(self, pf, x, y, w, h):
        """Draw playfield info panel"""
        pygame.draw.rect(self._surface, DebuggerColors.PANEL_BG, (x, y, w, h))
        pygame.draw.rect(self._surface, DebuggerColors.SPRITE_PF, (x, y, w, h), 2)

        py = y + 8
        title = self._font.render("PLAYFIELD", True, DebuggerColors.SPRITE_PF)
        self._surface.blit(title, (x + 10, py))
        py += 22

        info = [
            f"PF0: ${pf.pf0:02X}",
            f"PF1: ${pf.pf1:02X}",
            f"PF2: ${pf.pf2:02X}",
            f"Reflect: {'Yes' if pf.ctrlpf & 0x1 else 'No'}",
            f"Priority: {'PF' if pf.ctrlpf & 0x4 else 'Spr'}",
        ]

        for line in info:
            surf = self._small_font.render(line, True, DebuggerColors.TEXT)
            self._surface.blit(surf, (x + 10, py))
            py += 16

    def _draw_player_panel(self, title, player, color, x, y, w, h):
        """Draw detailed player panel"""
        pygame.draw.rect(self._surface, DebuggerColors.PANEL_BG, (x, y, w, h))
        pygame.draw.rect(self._surface, color, (x, y, w, h), 2)

        py = y + 10
        title_surf = self._font.render(title, True, color)
        self._surface.blit(title_surf, (x + 10, py))
        py += 25

        info = [
            f"GRP:   ${player.p:02X}  =  {player.p:08b}",
            f"RESP:  {player.resp:3d}  (horizontal position)",
            f"NUSIZ: ${player.nusiz:02X}  (size/copies)",
            f"REFP:  ${player.refp:02X}  (reflect: {'Yes' if player.refp & 0x8 else 'No'})",
            f"VDELP: ${player.vdelp:02X}  (vertical delay)",
        ]

        for line in info:
            surf = self._small_font.render(line, True, DebuggerColors.TEXT)
            self._surface.blit(surf, (x + 15, py))
            py += 18

        # Draw graphic visualization
        py += 5
        label = self._small_font.render("Graphic:", True, DebuggerColors.TEXT)
        self._surface.blit(label, (x + 15, py))

        # Draw 8-bit pattern large
        gx = x + 90
        reflect = (player.refp & 0x8) != 0
        for i in range(8):
            bit_idx = i if reflect else (7 - i)
            if (player.p >> bit_idx) & 1:
                pygame.draw.rect(self._surface, color, (gx + i * 12, py, 10, 20))
            else:
                pygame.draw.rect(self._surface, DebuggerColors.PANEL_BG, (gx + i * 12, py, 10, 20))
                pygame.draw.rect(self._surface, DebuggerColors.BORDER, (gx + i * 12, py, 10, 20), 1)

    def _draw_missile_panel_full(self, title, missile, color, x, y, w, h):
        """Draw missile panel"""
        pygame.draw.rect(self._surface, DebuggerColors.PANEL_BG, (x, y, w, h))
        pygame.draw.rect(self._surface, color, (x, y, w, h), 2)

        py = y + 10
        title_surf = self._font.render(title, True, color)
        self._surface.blit(title_surf, (x + 10, py))
        py += 25

        enabled = "ENABLED" if missile.enam & 0x02 else "disabled"
        info = [
            f"ENAM:  ${missile.enam:02X}  ({enabled})",
            f"RESM:  {missile.resm:3d}  (position)",
            f"NUSIZ: ${missile.nusiz:02X}  (size)",
        ]

        for line in info:
            surf = self._small_font.render(line, True, DebuggerColors.TEXT)
            self._surface.blit(surf, (x + 15, py))
            py += 18

    def _draw_ball_panel_full(self, title, ball, color, x, y, w, h):
        """Draw ball panel"""
        pygame.draw.rect(self._surface, DebuggerColors.PANEL_BG, (x, y, w, h))
        pygame.draw.rect(self._surface, color, (x, y, w, h), 2)

        py = y + 10
        title_surf = self._font.render(title, True, color)
        self._surface.blit(title_surf, (x + 10, py))
        py += 25

        enabled = "ENABLED" if ball.enabl & 0x02 else "disabled"
        width = 1 << ((ball.ctrlpf & 0x30) >> 4)
        info = [
            f"ENABL: ${ball.enabl:02X}  ({enabled})",
            f"RESBL: {ball.resbl:3d}  (position)",
            f"Width: {width} pixel(s)",
        ]

        for line in info:
            surf = self._small_font.render(line, True, DebuggerColors.TEXT)
            self._surface.blit(surf, (x + 15, py))
            py += 18

    def _draw_playfield_panel_full(self, pf, x, y, w, h):
        """Draw playfield panel"""
        pygame.draw.rect(self._surface, DebuggerColors.PANEL_BG, (x, y, w, h))
        pygame.draw.rect(self._surface, DebuggerColors.SPRITE_PF, (x, y, w, h), 2)

        py = y + 10
        title_surf = self._font.render("PLAYFIELD", True, DebuggerColors.SPRITE_PF)
        self._surface.blit(title_surf, (x + 10, py))
        py += 25

        # Registers
        info = [
            f"PF0: ${pf.pf0:02X} = {pf.pf0:08b}  (bits 4-7 used, reversed)",
            f"PF1: ${pf.pf1:02X} = {pf.pf1:08b}  (normal order)",
            f"PF2: ${pf.pf2:02X} = {pf.pf2:08b}  (reversed order)",
            f"CTRLPF: ${pf.ctrlpf:02X}  Reflect:{pf.ctrlpf & 0x1}  Score:{(pf.ctrlpf >> 1) & 0x1}  Priority:{(pf.ctrlpf >> 2) & 0x1}",
        ]

        for line in info:
            surf = self._small_font.render(line, True, DebuggerColors.TEXT)
            self._surface.blit(surf, (x + 15, py))
            py += 18

        # Visual representation
        py += 10
        label = self._small_font.render("Pattern (160 pixels):", True, DebuggerColors.TEXT)
        self._surface.blit(label, (x + 15, py))
        py += 18

        # Draw playfield pattern
        pf_scan = pf.get_playfield_scan()
        scale = 6
        for i in range(160):
            if i < len(pf_scan) and pf_scan[i]:
                pygame.draw.rect(self._surface, DebuggerColors.SPRITE_PF,
                               (x + 15 + i * scale, py, scale - 1, 16))

    def _draw_tia_view(self):
        """Draw TIA registers view"""
        stella = self.atari.stella
        y = 45

        # Colors panel
        self._draw_colors_panel(stella, 10, y, 320, 200)

        # Collision panel
        self._draw_collision_panel(stella, 340, y, 320, 200)

        # Motion panel
        self._draw_motion_panel(stella, 670, y, 320, 200)
        y += 210

        # RIOT panel
        self._draw_riot_panel(10, y, 490, 180)

        # Input panel
        self._draw_input_panel(510, y, 480, 180)

    def _draw_colors_panel(self, stella, x, y, w, h):
        """Draw color registers panel"""
        pygame.draw.rect(self._surface, DebuggerColors.PANEL_BG, (x, y, w, h))
        pygame.draw.rect(self._surface, DebuggerColors.BORDER, (x, y, w, h), 1)

        py = y + 10
        title = self._font.render("COLOR REGISTERS", True, DebuggerColors.TITLE)
        self._surface.blit(title, (x + 10, py))
        py += 30

        colors = [
            ("COLUP0", stella.nextLine.pColor[0], "Player 0"),
            ("COLUP1", stella.nextLine.pColor[1], "Player 1"),
            ("COLUPF", stella.nextLine.playfieldColor, "Playfield"),
            ("COLUBK", stella.nextLine.backgroundColor, "Background"),
        ]

        for name, val, desc in colors:
            name_surf = self._small_font.render(f"{name}:", True, DebuggerColors.REGISTER_NAME)
            self._surface.blit(name_surf, (x + 15, py))

            # Color swatch
            rgb = self._int_to_rgb(val)
            pygame.draw.rect(self._surface, rgb, (x + 80, py, 40, 16))
            pygame.draw.rect(self._surface, DebuggerColors.BORDER, (x + 80, py, 40, 16), 1)

            # Value and description
            val_surf = self._small_font.render(f"${val:06X}  {desc}", True, DebuggerColors.TEXT)
            self._surface.blit(val_surf, (x + 130, py))
            py += 22

    def _draw_collision_panel(self, stella, x, y, w, h):
        """Draw collision registers panel"""
        pygame.draw.rect(self._surface, DebuggerColors.PANEL_BG, (x, y, w, h))
        pygame.draw.rect(self._surface, DebuggerColors.BORDER, (x, y, w, h), 1)

        py = y + 10
        title = self._font.render("COLLISIONS", True, DebuggerColors.TITLE)
        self._surface.blit(title, (x + 10, py))
        py += 30

        coll = stella._collision_state
        collisions = [
            ("CXM0P", coll._cxmp[0], "M0-P1, M0-P0"),
            ("CXM1P", coll._cxmp[1], "M1-P0, M1-P1"),
            ("CXP0FB", coll._cxpfb[0], "P0-PF, P0-BL"),
            ("CXP1FB", coll._cxpfb[1], "P1-PF, P1-BL"),
            ("CXM0FB", coll._cxmfb[0], "M0-PF, M0-BL"),
            ("CXM1FB", coll._cxmfb[1], "M1-PF, M1-BL"),
            ("CXBLPF", coll._cxblpf, "BL-PF"),
            ("CXPPMM", coll._cxppmm, "P0-P1, M0-M1"),
        ]

        for name, val, desc in collisions:
            color = DebuggerColors.CHANGED if val else DebuggerColors.VALUE
            text = f"{name}: ${val:02X}  {desc}"
            surf = self._small_font.render(text, True, color)
            self._surface.blit(surf, (x + 15, py))
            py += 18

    def _draw_motion_panel(self, stella, x, y, w, h):
        """Draw horizontal motion panel"""
        pygame.draw.rect(self._surface, DebuggerColors.PANEL_BG, (x, y, w, h))
        pygame.draw.rect(self._surface, DebuggerColors.BORDER, (x, y, w, h), 1)

        py = y + 10
        title = self._font.render("HORIZONTAL MOTION", True, DebuggerColors.TITLE)
        self._surface.blit(title, (x + 10, py))
        py += 30

        hm = stella.nextLine
        motions = [
            ("HMP0", hm.hmp[0], "Player 0"),
            ("HMP1", hm.hmp[1], "Player 1"),
            ("HMM0", hm.hmm[0], "Missile 0"),
            ("HMM1", hm.hmm[1], "Missile 1"),
            ("HMBL", hm.hmbl, "Ball"),
        ]

        for name, val, desc in motions:
            text = f"{name}: ${val:02X}  {desc}"
            surf = self._small_font.render(text, True, DebuggerColors.TEXT)
            self._surface.blit(surf, (x + 15, py))
            py += 20

    def _draw_riot_panel(self, x, y, w, h):
        """Draw RIOT/timer panel"""
        pygame.draw.rect(self._surface, DebuggerColors.PANEL_BG, (x, y, w, h))
        pygame.draw.rect(self._surface, DebuggerColors.BORDER, (x, y, w, h), 1)

        py = y + 10
        title = self._font.render("RIOT / TIMER", True, DebuggerColors.TITLE)
        self._surface.blit(title, (x + 10, py))
        py += 30

        riot = self.atari.riot
        clk = self.atari.clocks.system_clock

        info = [
            f"Timer Interval: {riot.interval}x",
            f"Set Time:       {riot.set_time}",
            f"Expiration:     {riot.expiration_time}",
            f"Current Clock:  {clk}",
            f"Time Remaining: {max(0, riot.expiration_time - clk)}",
        ]

        for line in info:
            surf = self._small_font.render(line, True, DebuggerColors.TEXT)
            self._surface.blit(surf, (x + 15, py))
            py += 20

    def _draw_input_panel(self, x, y, w, h):
        """Draw input state panel"""
        pygame.draw.rect(self._surface, DebuggerColors.PANEL_BG, (x, y, w, h))
        pygame.draw.rect(self._surface, DebuggerColors.BORDER, (x, y, w, h), 1)

        py = y + 10
        title = self._font.render("INPUT STATE", True, DebuggerColors.TITLE)
        self._surface.blit(title, (x + 10, py))
        py += 30

        inputs = self.atari.inputs

        # Joystick
        joy = []
        if not (inputs.swcha & 0x10): joy.append("UP")
        if not (inputs.swcha & 0x20): joy.append("DOWN")
        if not (inputs.swcha & 0x40): joy.append("LEFT")
        if not (inputs.swcha & 0x80): joy.append("RIGHT")
        if not (inputs.input7 & 0x80): joy.append("FIRE")

        info = [
            f"SWCHA:  ${inputs.swcha:02X}  = {inputs.swcha:08b}",
            f"SWCHB:  ${inputs.swchb:02X}  = {inputs.swchb:08b}",
            f"INPUT7: ${inputs.input7:02X}",
            f"",
            f"Active: {', '.join(joy) if joy else '(none)'}",
            f"Select: {'PRESSED' if not (inputs.swchb & 0x1) else 'off'}",
            f"Reset:  {'PRESSED' if not (inputs.swchb & 0x2) else 'off'}",
        ]

        for line in info:
            color = DebuggerColors.HIGHLIGHT if 'PRESSED' in line or (joy and 'Active' in line) else DebuggerColors.TEXT
            surf = self._small_font.render(line, True, color)
            self._surface.blit(surf, (x + 15, py))
            py += 18

    def _int_to_rgb(self, color_int):
        """Convert packed RGB integer to tuple"""
        r = (color_int >> 16) & 0xFF
        g = (color_int >> 8) & 0xFF
        b = color_int & 0xFF
        return (r, g, b)

    def _is_changed(self, reg, current_val):
        """Check if register value changed"""
        if self._prev_cpu_state is None:
            return False
        return self._prev_cpu_state.get(reg) != current_val

    def step(self):
        """Called each frame to update debugger"""
        if not self.active:
            return
        if not self.paused:
            self._capture_state()
