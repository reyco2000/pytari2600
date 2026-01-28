"""
Atari 2600 Debugger Module

Provides interactive debugging capabilities:
- Memory viewer (hex dump)
- CPU status viewer
- Sprite/TIA state viewer
- Memory dump to file
- Breakpoint support

Press F12 to toggle debugger on/off during emulation.
Use keyboard to navigate while debugger is active.
"""

import pygame
import os
from datetime import datetime


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


class Debugger:
    """
    Interactive debugger for the Atari 2600 emulator.

    Features:
    - Memory hex dump viewer with scrolling
    - CPU register and flag display
    - TIA sprite state visualization
    - Memory dump to file
    - Real-time state monitoring
    """

    # Display constants
    DEBUGGER_WIDTH = 800
    DEBUGGER_HEIGHT = 600
    FONT_SIZE = 14
    SMALL_FONT_SIZE = 12
    LINE_HEIGHT = 18
    PANEL_PADDING = 10

    # Memory view constants
    BYTES_PER_LINE = 16
    MEMORY_LINES = 16

    # View modes
    VIEW_MEMORY = 0
    VIEW_CPU = 1
    VIEW_SPRITES = 2
    VIEW_TIA = 3

    def __init__(self, atari):
        """
        Initialize the debugger.

        Args:
            atari: Reference to the main Atari object
        """
        self.atari = atari
        self.active = False
        self.paused = False
        self.view_mode = self.VIEW_CPU

        # Memory viewer state
        self.memory_offset = 0x0000
        self.memory_region = 'ram'  # 'ram', 'rom', 'tia', 'riot'

        # Previous state for change detection
        self._prev_cpu_state = None
        self._prev_memory = None

        # Breakpoints
        self.breakpoints = set()
        self.watch_addresses = set()

        # Display surface (will be created when needed)
        self._surface = None
        self._font = None
        self._small_font = None
        self._initialized = False

    def _init_display(self):
        """Initialize pygame fonts and surfaces for debugger display"""
        if self._initialized:
            return

        pygame.font.init()
        self._font = pygame.font.SysFont('monospace', self.FONT_SIZE)
        self._small_font = pygame.font.SysFont('monospace', self.SMALL_FONT_SIZE)
        self._surface = pygame.Surface((self.DEBUGGER_WIDTH, self.DEBUGGER_HEIGHT))
        self._initialized = True

    def toggle(self):
        """Toggle debugger active state"""
        self.active = not self.active
        if self.active:
            self._init_display()
            self._capture_state()
            print("Debugger activated - Press F12 to close")
            print("  1: CPU view  2: Memory view  3: Sprites  4: TIA registers")
            print("  P: Pause/Resume  D: Dump memory  Up/Down: Scroll")
        else:
            print("Debugger deactivated")

    def toggle_pause(self):
        """Toggle emulation pause state"""
        self.paused = not self.paused
        print(f"Emulation {'paused' if self.paused else 'resumed'}")

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
        # Capture RAM state
        self._prev_memory = list(self.atari.riot.ram)

    def handle_key(self, key):
        """
        Handle debugger keyboard input.

        Args:
            key: pygame key constant
        """
        if key == pygame.K_1:
            self.view_mode = self.VIEW_CPU
        elif key == pygame.K_2:
            self.view_mode = self.VIEW_MEMORY
        elif key == pygame.K_3:
            self.view_mode = self.VIEW_SPRITES
        elif key == pygame.K_4:
            self.view_mode = self.VIEW_TIA
        elif key == pygame.K_p:
            self.toggle_pause()
        elif key == pygame.K_d:
            self.dump_memory()
        elif key == pygame.K_UP:
            self._scroll_up()
        elif key == pygame.K_DOWN:
            self._scroll_down()
        elif key == pygame.K_PAGEUP:
            self._page_up()
        elif key == pygame.K_PAGEDOWN:
            self._page_down()
        elif key == pygame.K_HOME:
            self.memory_offset = 0
        elif key == pygame.K_END:
            self._goto_end()
        elif key == pygame.K_TAB:
            self._cycle_memory_region()

    def _scroll_up(self):
        """Scroll memory view up one line"""
        self.memory_offset = max(0, self.memory_offset - self.BYTES_PER_LINE)

    def _scroll_down(self):
        """Scroll memory view down one line"""
        max_offset = self._get_max_offset()
        self.memory_offset = min(max_offset, self.memory_offset + self.BYTES_PER_LINE)

    def _page_up(self):
        """Scroll memory view up one page"""
        self.memory_offset = max(0, self.memory_offset - self.BYTES_PER_LINE * self.MEMORY_LINES)

    def _page_down(self):
        """Scroll memory view down one page"""
        max_offset = self._get_max_offset()
        self.memory_offset = min(max_offset, self.memory_offset + self.BYTES_PER_LINE * self.MEMORY_LINES)

    def _goto_end(self):
        """Go to end of current memory region"""
        self.memory_offset = self._get_max_offset()

    def _get_max_offset(self):
        """Get maximum scroll offset for current memory region"""
        if self.memory_region == 'ram':
            return max(0, 128 - self.BYTES_PER_LINE * self.MEMORY_LINES)
        elif self.memory_region == 'rom':
            cart = self.atari.memory.cartridge
            if hasattr(cart, 'rom') and cart.rom:
                return max(0, len(cart.rom) - self.BYTES_PER_LINE * self.MEMORY_LINES)
        return 0

    def _cycle_memory_region(self):
        """Cycle through memory regions"""
        regions = ['ram', 'rom', 'stack']
        idx = regions.index(self.memory_region) if self.memory_region in regions else 0
        self.memory_region = regions[(idx + 1) % len(regions)]
        self.memory_offset = 0
        print(f"Memory region: {self.memory_region.upper()}")

    def dump_memory(self):
        """Dump current memory state to a file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"memory_dump_{timestamp}.txt"

        with open(filename, 'w') as f:
            f.write("=" * 60 + "\n")
            f.write(f"Atari 2600 Memory Dump - {datetime.now()}\n")
            f.write("=" * 60 + "\n\n")

            # CPU State
            f.write("CPU STATE\n")
            f.write("-" * 40 + "\n")
            pc_state = self.atari.pc_state
            f.write(f"PC: ${pc_state.PC:04X}\n")
            f.write(f"A:  ${pc_state.A.value:02X}  X: ${pc_state.X.value:02X}  Y: ${pc_state.Y.value:02X}\n")
            f.write(f"SP: ${pc_state.S.value:02X}\n")
            f.write(f"Flags: N={pc_state.P.get_N()} V={pc_state.P.get_V()} ")
            f.write(f"B={pc_state.P.get_B()} D={pc_state.P.get_D()} ")
            f.write(f"I={pc_state.P.get_I()} Z={pc_state.P.get_Z()} C={pc_state.P.get_C()}\n\n")

            # RAM (RIOT)
            f.write("RAM (128 bytes @ $0080-$00FF)\n")
            f.write("-" * 40 + "\n")
            ram = self.atari.riot.ram
            for i in range(0, 128, 16):
                addr = 0x80 + i
                hex_str = ' '.join(f'{ram[i+j]:02X}' for j in range(min(16, 128-i)))
                ascii_str = ''.join(
                    chr(ram[i+j]) if 32 <= ram[i+j] < 127 else '.'
                    for j in range(min(16, 128-i))
                )
                f.write(f"${addr:04X}: {hex_str:<48} |{ascii_str}|\n")
            f.write("\n")

            # Stack
            f.write("STACK (@ $0100-$01FF)\n")
            f.write("-" * 40 + "\n")
            sp = pc_state.S.value
            f.write(f"Stack Pointer: ${sp:02X} (Top at ${0x100 + sp:04X})\n")
            # Show stack contents from SP to 0xFF
            for i in range(sp, 0x100, 16):
                addr = 0x100 + i
                end = min(i + 16, 0x100)
                hex_str = ' '.join(f'{ram[j & 0x7F]:02X}' for j in range(i, end))
                f.write(f"${addr:04X}: {hex_str}\n")
            f.write("\n")

            # ROM info
            f.write("ROM CARTRIDGE\n")
            f.write("-" * 40 + "\n")
            cart = self.atari.memory.cartridge
            if hasattr(cart, 'rom') and cart.rom:
                f.write(f"Size: {len(cart.rom)} bytes\n")
                # First 256 bytes of ROM
                f.write("\nFirst 256 bytes:\n")
                for i in range(0, min(256, len(cart.rom)), 16):
                    addr = 0x1000 + i
                    hex_str = ' '.join(f'{cart.rom[i+j]:02X}' for j in range(min(16, len(cart.rom)-i)))
                    f.write(f"${addr:04X}: {hex_str}\n")

                # Reset vector
                if len(cart.rom) >= 0xFFD:
                    reset_lo = cart.rom[0xFFC]
                    reset_hi = cart.rom[0xFFD]
                    reset_vector = (reset_hi << 8) | reset_lo
                    f.write(f"\nReset Vector: ${reset_vector:04X}\n")
            f.write("\n")

            # TIA State
            f.write("TIA STATE\n")
            f.write("-" * 40 + "\n")
            stella = self.atari.stella
            f.write(f"Player 0: GRP=${stella.p0_state.p:02X} RESP={stella.p0_state.resp} ")
            f.write(f"NUSIZ=${stella.p0_state.nusiz:02X}\n")
            f.write(f"Player 1: GRP=${stella.p1_state.p:02X} RESP={stella.p1_state.resp} ")
            f.write(f"NUSIZ=${stella.p1_state.nusiz:02X}\n")
            f.write(f"Missile 0: ENAM=${stella.missile0.enam:02X} RESM={stella.missile0.resm}\n")
            f.write(f"Missile 1: ENAM=${stella.missile1.enam:02X} RESM={stella.missile1.resm}\n")
            f.write(f"Ball: ENABL=${stella.ball.enabl:02X} RESBL={stella.ball.resbl}\n")
            f.write(f"Playfield: PF0=${stella.playfield_state.pf0:02X} ")
            f.write(f"PF1=${stella.playfield_state.pf1:02X} PF2=${stella.playfield_state.pf2:02X}\n")

            # Clock info
            f.write("\nTIMING\n")
            f.write("-" * 40 + "\n")
            f.write(f"System Clock: {self.atari.clocks.system_clock}\n")

        print(f"Memory dumped to {filename}")
        return filename

    def render(self, screen):
        """
        Render the debugger overlay.

        Args:
            screen: pygame display surface to render onto
        """
        if not self.active:
            return

        self._init_display()
        self._surface.fill(DebuggerColors.BACKGROUND)

        # Draw title bar
        self._draw_title_bar()

        # Draw based on view mode
        if self.view_mode == self.VIEW_CPU:
            self._draw_cpu_view()
        elif self.view_mode == self.VIEW_MEMORY:
            self._draw_memory_view()
        elif self.view_mode == self.VIEW_SPRITES:
            self._draw_sprite_view()
        elif self.view_mode == self.VIEW_TIA:
            self._draw_tia_view()

        # Draw help bar at bottom
        self._draw_help_bar()

        # Blit debugger surface onto main screen
        # Center the debugger window
        x = (screen.get_width() - self.DEBUGGER_WIDTH) // 2
        y = (screen.get_height() - self.DEBUGGER_HEIGHT) // 2
        screen.blit(self._surface, (x, y))

    def _draw_title_bar(self):
        """Draw the debugger title bar"""
        # Title background
        pygame.draw.rect(self._surface, DebuggerColors.PANEL_BG,
                        (0, 0, self.DEBUGGER_WIDTH, 30))
        pygame.draw.line(self._surface, DebuggerColors.BORDER,
                        (0, 30), (self.DEBUGGER_WIDTH, 30), 2)

        # Title text
        title = "ATARI 2600 DEBUGGER"
        if self.paused:
            title += " [PAUSED]"
        title_surf = self._font.render(title, True, DebuggerColors.TITLE)
        self._surface.blit(title_surf, (self.PANEL_PADDING, 6))

        # View mode tabs
        modes = ["1:CPU", "2:MEM", "3:SPR", "4:TIA"]
        tab_x = 300
        for i, mode in enumerate(modes):
            color = DebuggerColors.HIGHLIGHT if i == self.view_mode else DebuggerColors.TEXT
            tab_surf = self._font.render(mode, True, color)
            self._surface.blit(tab_surf, (tab_x, 6))
            tab_x += 80

    def _draw_help_bar(self):
        """Draw help text at bottom of debugger"""
        y = self.DEBUGGER_HEIGHT - 25
        pygame.draw.rect(self._surface, DebuggerColors.PANEL_BG,
                        (0, y, self.DEBUGGER_WIDTH, 25))
        pygame.draw.line(self._surface, DebuggerColors.BORDER,
                        (0, y), (self.DEBUGGER_WIDTH, y), 1)

        if self.view_mode == self.VIEW_MEMORY:
            help_text = "Up/Down:Scroll  PgUp/PgDn:Page  Tab:Region  Home/End  D:Dump  P:Pause  F12:Close"
        else:
            help_text = "1-4:Views  P:Pause/Resume  D:Dump Memory  F12:Close Debugger"

        help_surf = self._small_font.render(help_text, True, DebuggerColors.TEXT)
        self._surface.blit(help_surf, (self.PANEL_PADDING, y + 5))

    def _draw_cpu_view(self):
        """Draw CPU registers and status"""
        pc_state = self.atari.pc_state
        y = 50

        # Panel title
        title_surf = self._font.render("CPU REGISTERS", True, DebuggerColors.TITLE)
        self._surface.blit(title_surf, (self.PANEL_PADDING, y))
        y += 30

        # Draw panel background
        panel_rect = (self.PANEL_PADDING, y, 380, 200)
        pygame.draw.rect(self._surface, DebuggerColors.PANEL_BG, panel_rect)
        pygame.draw.rect(self._surface, DebuggerColors.BORDER, panel_rect, 1)
        y += 15

        # Program Counter
        self._draw_register("PC", f"${pc_state.PC:04X}", 20, y,
                           self._is_changed('PC', pc_state.PC))
        y += self.LINE_HEIGHT

        # Accumulator
        self._draw_register("A", f"${pc_state.A.value:02X}", 20, y,
                           self._is_changed('A', pc_state.A.value))
        # Also show decimal and binary
        dec_surf = self._small_font.render(f"({pc_state.A.value:3d}) {pc_state.A.value:08b}",
                                           True, DebuggerColors.TEXT)
        self._surface.blit(dec_surf, (150, y))
        y += self.LINE_HEIGHT

        # X Register
        self._draw_register("X", f"${pc_state.X.value:02X}", 20, y,
                           self._is_changed('X', pc_state.X.value))
        dec_surf = self._small_font.render(f"({pc_state.X.value:3d}) {pc_state.X.value:08b}",
                                           True, DebuggerColors.TEXT)
        self._surface.blit(dec_surf, (150, y))
        y += self.LINE_HEIGHT

        # Y Register
        self._draw_register("Y", f"${pc_state.Y.value:02X}", 20, y,
                           self._is_changed('Y', pc_state.Y.value))
        dec_surf = self._small_font.render(f"({pc_state.Y.value:3d}) {pc_state.Y.value:08b}",
                                           True, DebuggerColors.TEXT)
        self._surface.blit(dec_surf, (150, y))
        y += self.LINE_HEIGHT

        # Stack Pointer
        self._draw_register("SP", f"${pc_state.S.value:02X}", 20, y,
                           self._is_changed('S', pc_state.S.value))
        stack_addr = 0x100 + pc_state.S.value
        stack_surf = self._small_font.render(f"(Stack top: ${stack_addr:04X})",
                                             True, DebuggerColors.TEXT)
        self._surface.blit(stack_surf, (150, y))
        y += self.LINE_HEIGHT * 2

        # Status Flags
        flags_title = self._font.render("STATUS FLAGS (P)", True, DebuggerColors.TITLE)
        self._surface.blit(flags_title, (20, y))
        y += 25

        flags = [
            ('N', 'Negative', pc_state.P.get_N()),
            ('V', 'Overflow', pc_state.P.get_V()),
            ('-', 'Unused', 1),
            ('B', 'Break', pc_state.P.get_B()),
            ('D', 'Decimal', pc_state.P.get_D()),
            ('I', 'IRQ Disable', pc_state.P.get_I()),
            ('Z', 'Zero', pc_state.P.get_Z()),
            ('C', 'Carry', pc_state.P.get_C()),
        ]

        flag_x = 20
        for flag_char, flag_name, flag_val in flags:
            color = DebuggerColors.FLAG_SET if flag_val else DebuggerColors.FLAG_CLEAR
            flag_surf = self._font.render(flag_char, True, color)
            self._surface.blit(flag_surf, (flag_x, y))
            flag_x += 25

        y += self.LINE_HEIGHT

        # Flag values as binary
        flag_val = pc_state.P.value
        bin_surf = self._small_font.render(f"P = ${flag_val:02X} = {flag_val:08b}",
                                           True, DebuggerColors.TEXT)
        self._surface.blit(bin_surf, (20, y))

        # Right panel - Clock and timing info
        y = 50
        x = 420

        title_surf = self._font.render("TIMING", True, DebuggerColors.TITLE)
        self._surface.blit(title_surf, (x, y))
        y += 30

        panel_rect = (x, y, 360, 100)
        pygame.draw.rect(self._surface, DebuggerColors.PANEL_BG, panel_rect)
        pygame.draw.rect(self._surface, DebuggerColors.BORDER, panel_rect, 1)
        y += 15

        clk = self.atari.clocks.system_clock
        self._draw_register("Clock", f"{clk}", x + 10, y, False)
        y += self.LINE_HEIGHT

        cpu_cycles = clk // 3
        self._draw_register("CPU Cycles", f"{cpu_cycles}", x + 10, y, False)
        y += self.LINE_HEIGHT

        # Scanline info
        stella = self.atari.stella
        scan_clk = clk - stella._screen_start_clock
        scanline = scan_clk // stella.HORIZONTAL_TICKS
        hpos = scan_clk % stella.HORIZONTAL_TICKS
        self._draw_register("Scanline", f"{scanline}", x + 10, y, False)
        y += self.LINE_HEIGHT
        self._draw_register("H-Pos", f"{hpos}", x + 10, y, False)

        # Stack view
        y = 290
        title_surf = self._font.render("STACK", True, DebuggerColors.TITLE)
        self._surface.blit(title_surf, (self.PANEL_PADDING, y))
        y += 25

        panel_rect = (self.PANEL_PADDING, y, 380, 250)
        pygame.draw.rect(self._surface, DebuggerColors.PANEL_BG, panel_rect)
        pygame.draw.rect(self._surface, DebuggerColors.BORDER, panel_rect, 1)
        y += 10

        sp = pc_state.S.value
        ram = self.atari.riot.ram
        stack_lines = min(12, 0xFF - sp)
        for i in range(stack_lines):
            addr = 0x100 + sp + 1 + i
            val = ram[(sp + 1 + i) & 0x7F]
            line = f"${addr:04X}: ${val:02X}"
            color = DebuggerColors.ADDRESS if i == 0 else DebuggerColors.TEXT
            line_surf = self._small_font.render(line, True, color)
            self._surface.blit(line_surf, (20, y))
            y += 16

    def _draw_register(self, name, value, x, y, changed=False):
        """Draw a register name and value"""
        name_surf = self._font.render(f"{name}:", True, DebuggerColors.REGISTER_NAME)
        self._surface.blit(name_surf, (x, y))

        color = DebuggerColors.CHANGED if changed else DebuggerColors.VALUE
        val_surf = self._font.render(value, True, color)
        self._surface.blit(val_surf, (x + 80, y))

    def _is_changed(self, reg, current_val):
        """Check if a register value has changed since last capture"""
        if self._prev_cpu_state is None:
            return False
        return self._prev_cpu_state.get(reg) != current_val

    def _draw_memory_view(self):
        """Draw memory hex dump view"""
        y = 50

        # Title with region info
        title = f"MEMORY VIEW - {self.memory_region.upper()}"
        title_surf = self._font.render(title, True, DebuggerColors.TITLE)
        self._surface.blit(title_surf, (self.PANEL_PADDING, y))
        y += 30

        # Panel background
        panel_rect = (self.PANEL_PADDING, y, self.DEBUGGER_WIDTH - 2*self.PANEL_PADDING, 480)
        pygame.draw.rect(self._surface, DebuggerColors.PANEL_BG, panel_rect)
        pygame.draw.rect(self._surface, DebuggerColors.BORDER, panel_rect, 1)
        y += 15

        # Header
        header = "Address   " + " ".join(f"{i:02X}" for i in range(16)) + "  ASCII"
        header_surf = self._small_font.render(header, True, DebuggerColors.ADDRESS)
        self._surface.blit(header_surf, (20, y))
        y += self.LINE_HEIGHT + 5

        # Get memory data based on region
        if self.memory_region == 'ram':
            data = self.atari.riot.ram
            base_addr = 0x80
            max_size = 128
        elif self.memory_region == 'rom':
            cart = self.atari.memory.cartridge
            data = cart.rom if hasattr(cart, 'rom') and cart.rom else []
            base_addr = 0x1000
            max_size = len(data)
        elif self.memory_region == 'stack':
            data = self.atari.riot.ram
            base_addr = 0x100
            max_size = 128
        else:
            data = []
            base_addr = 0
            max_size = 0

        # Draw memory lines
        for line in range(self.MEMORY_LINES):
            offset = self.memory_offset + line * self.BYTES_PER_LINE
            if offset >= max_size:
                break

            addr = base_addr + offset

            # Address
            addr_text = f"${addr:04X}:"
            addr_surf = self._small_font.render(addr_text, True, DebuggerColors.ADDRESS)
            self._surface.blit(addr_surf, (20, y))

            # Hex values
            hex_x = 90
            ascii_str = ""
            for i in range(self.BYTES_PER_LINE):
                idx = offset + i
                if idx < max_size:
                    if self.memory_region == 'stack':
                        val = data[idx & 0x7F]
                    else:
                        val = data[idx] if idx < len(data) else 0

                    # Check if value changed
                    changed = False
                    if self.memory_region == 'ram' and self._prev_memory:
                        if idx < len(self._prev_memory):
                            changed = self._prev_memory[idx] != val

                    color = DebuggerColors.CHANGED if changed else DebuggerColors.VALUE
                    hex_surf = self._small_font.render(f"{val:02X}", True, color)
                    self._surface.blit(hex_surf, (hex_x, y))

                    # ASCII character
                    ascii_str += chr(val) if 32 <= val < 127 else '.'
                else:
                    hex_surf = self._small_font.render("  ", True, DebuggerColors.TEXT)
                    self._surface.blit(hex_surf, (hex_x, y))
                    ascii_str += ' '

                hex_x += 24

            # ASCII representation
            ascii_surf = self._small_font.render(f"|{ascii_str}|", True, DebuggerColors.TEXT)
            self._surface.blit(ascii_surf, (hex_x + 10, y))

            y += self.LINE_HEIGHT

        # Scroll indicator
        y = 520
        if max_size > 0:
            progress = self.memory_offset / max(1, max_size - self.BYTES_PER_LINE * self.MEMORY_LINES)
            progress = min(1.0, max(0.0, progress))
            indicator = f"Offset: ${self.memory_offset:04X} / ${max_size:04X} ({progress*100:.0f}%)"
        else:
            indicator = "No data"
        ind_surf = self._small_font.render(indicator, True, DebuggerColors.TEXT)
        self._surface.blit(ind_surf, (20, y))

    def _draw_sprite_view(self):
        """Draw sprite/player graphics state"""
        stella = self.atari.stella
        y = 50

        title_surf = self._font.render("SPRITES / GRAPHICS OBJECTS", True, DebuggerColors.TITLE)
        self._surface.blit(title_surf, (self.PANEL_PADDING, y))
        y += 30

        # Player 0
        self._draw_sprite_panel("PLAYER 0", stella.p0_state, DebuggerColors.SPRITE_P0,
                               self.PANEL_PADDING, y, 380, 120)

        # Player 1
        self._draw_sprite_panel("PLAYER 1", stella.p1_state, DebuggerColors.SPRITE_P1,
                               410, y, 380, 120)
        y += 140

        # Missiles
        self._draw_missile_panel("MISSILE 0", stella.missile0, DebuggerColors.SPRITE_M0,
                                self.PANEL_PADDING, y, 185, 100)
        self._draw_missile_panel("MISSILE 1", stella.missile1, DebuggerColors.SPRITE_M1,
                                205, y, 185, 100)

        # Ball
        self._draw_ball_panel("BALL", stella.ball, DebuggerColors.SPRITE_BALL,
                             410, y, 185, 100)
        y += 120

        # Playfield
        self._draw_playfield_panel("PLAYFIELD", stella.playfield_state, DebuggerColors.SPRITE_PF,
                                  self.PANEL_PADDING, y, 780, 140)

        # Draw sprite graphics visualization
        y += 160
        self._draw_sprite_graphics(stella, y)

    def _draw_sprite_panel(self, title, player_state, color, x, y, w, h):
        """Draw a player sprite info panel"""
        pygame.draw.rect(self._surface, DebuggerColors.PANEL_BG, (x, y, w, h))
        pygame.draw.rect(self._surface, color, (x, y, w, h), 2)

        title_surf = self._small_font.render(title, True, color)
        self._surface.blit(title_surf, (x + 10, y + 5))

        info_y = y + 25
        info = [
            f"GRP:  ${player_state.p:02X}  ({player_state.p:08b})",
            f"RESP: {player_state.resp:3d}  NUSIZ: ${player_state.nusiz:02X}",
            f"REFP: ${player_state.refp:02X}  VDELP: ${player_state.vdelp:02X}",
        ]

        for line in info:
            line_surf = self._small_font.render(line, True, DebuggerColors.TEXT)
            self._surface.blit(line_surf, (x + 10, info_y))
            info_y += 16

        # Draw graphic pattern
        self._draw_graphic_pattern(player_state.p, x + 10, info_y + 5, color,
                                   reflect=(player_state.refp & 0x8) != 0)

    def _draw_missile_panel(self, title, missile_state, color, x, y, w, h):
        """Draw missile info panel"""
        pygame.draw.rect(self._surface, DebuggerColors.PANEL_BG, (x, y, w, h))
        pygame.draw.rect(self._surface, color, (x, y, w, h), 2)

        title_surf = self._small_font.render(title, True, color)
        self._surface.blit(title_surf, (x + 5, y + 5))

        enabled = "ON" if missile_state.enam & 0x02 else "OFF"
        info = [
            f"ENAM: ${missile_state.enam:02X} ({enabled})",
            f"RESM: {missile_state.resm:3d}",
            f"NUSIZ: ${missile_state.nusiz:02X}",
        ]

        info_y = y + 25
        for line in info:
            line_surf = self._small_font.render(line, True, DebuggerColors.TEXT)
            self._surface.blit(line_surf, (x + 5, info_y))
            info_y += 16

    def _draw_ball_panel(self, title, ball_state, color, x, y, w, h):
        """Draw ball info panel"""
        pygame.draw.rect(self._surface, DebuggerColors.PANEL_BG, (x, y, w, h))
        pygame.draw.rect(self._surface, color, (x, y, w, h), 2)

        title_surf = self._small_font.render(title, True, color)
        self._surface.blit(title_surf, (x + 5, y + 5))

        enabled = "ON" if ball_state.enabl & 0x02 else "OFF"
        width = 1 << ((ball_state.ctrlpf & 0x30) >> 4)
        info = [
            f"ENABL: ${ball_state.enabl:02X} ({enabled})",
            f"RESBL: {ball_state.resbl:3d}",
            f"Width: {width}px",
        ]

        info_y = y + 25
        for line in info:
            line_surf = self._small_font.render(line, True, DebuggerColors.TEXT)
            self._surface.blit(line_surf, (x + 5, info_y))
            info_y += 16

    def _draw_playfield_panel(self, title, pf_state, color, x, y, w, h):
        """Draw playfield info panel"""
        pygame.draw.rect(self._surface, DebuggerColors.PANEL_BG, (x, y, w, h))
        pygame.draw.rect(self._surface, color, (x, y, w, h), 2)

        title_surf = self._small_font.render(title, True, color)
        self._surface.blit(title_surf, (x + 10, y + 5))

        info_y = y + 25
        info = [
            f"PF0: ${pf_state.pf0:02X} ({pf_state.pf0:08b})  "
            f"PF1: ${pf_state.pf1:02X} ({pf_state.pf1:08b})  "
            f"PF2: ${pf_state.pf2:02X} ({pf_state.pf2:08b})",
            f"CTRLPF: ${pf_state.ctrlpf:02X}  "
            f"Reflect: {'Yes' if pf_state.ctrlpf & 0x1 else 'No'}  "
            f"Score mode: {'Yes' if pf_state.ctrlpf & 0x2 else 'No'}  "
            f"Priority: {'PF' if pf_state.ctrlpf & 0x4 else 'Player'}",
        ]

        for line in info:
            line_surf = self._small_font.render(line, True, DebuggerColors.TEXT)
            self._surface.blit(line_surf, (x + 10, info_y))
            info_y += 16

        # Draw playfield pattern
        self._draw_playfield_pattern(pf_state, x + 10, info_y + 10, color)

    def _draw_graphic_pattern(self, grp, x, y, color, reflect=False, scale=3):
        """Draw an 8-bit graphic pattern as pixels"""
        for i in range(8):
            bit_idx = i if reflect else (7 - i)
            if (grp >> bit_idx) & 1:
                pygame.draw.rect(self._surface, color,
                               (x + i * scale, y, scale - 1, scale * 2))
            else:
                pygame.draw.rect(self._surface, DebuggerColors.PANEL_BG,
                               (x + i * scale, y, scale - 1, scale * 2))

    def _draw_playfield_pattern(self, pf_state, x, y, color):
        """Draw the playfield pattern visualization"""
        scale = 4
        pf_scan = pf_state.get_playfield_scan()

        # Draw each pixel of the 160-pixel playfield (scaled down)
        for i in range(0, 160, 2):  # Sample every other pixel
            if i < len(pf_scan) and pf_scan[i]:
                pygame.draw.rect(self._surface, color,
                               (x + (i // 2) * scale, y, scale - 1, 8))

    def _draw_sprite_graphics(self, stella, y):
        """Draw actual sprite scan lines visualization"""
        x = self.PANEL_PADDING

        title_surf = self._small_font.render("SCANLINE PREVIEW (current sprite positions)",
                                             True, DebuggerColors.TITLE)
        self._surface.blit(title_surf, (x, y))
        y += 20

        # Draw a 160-pixel wide preview
        scale = 4
        width = 160 * scale

        # Background
        pygame.draw.rect(self._surface, (40, 40, 50), (x, y, width, 20))

        # Get scan data
        p0_scan = stella.p0_state.get_player_scan()
        p1_scan = stella.p1_state.get_player_scan()
        m0_scan = stella.missile0.get_missile_scan()
        m1_scan = stella.missile1.get_missile_scan()
        bl_scan = stella.ball.get_ball_scan()
        pf_scan = stella.playfield_state.get_playfield_scan()

        # Draw sprites (layered)
        for i in range(160):
            px = x + i * scale
            if i < len(pf_scan) and pf_scan[i]:
                pygame.draw.rect(self._surface, DebuggerColors.SPRITE_PF, (px, y, scale-1, 20))
            if i < len(bl_scan) and bl_scan[i]:
                pygame.draw.rect(self._surface, DebuggerColors.SPRITE_BALL, (px, y+2, scale-1, 16))
            if i < len(m1_scan) and m1_scan[i]:
                pygame.draw.rect(self._surface, DebuggerColors.SPRITE_M1, (px, y+4, scale-1, 12))
            if i < len(m0_scan) and m0_scan[i]:
                pygame.draw.rect(self._surface, DebuggerColors.SPRITE_M0, (px, y+4, scale-1, 12))
            if i < len(p1_scan) and p1_scan[i]:
                pygame.draw.rect(self._surface, DebuggerColors.SPRITE_P1, (px, y+6, scale-1, 8))
            if i < len(p0_scan) and p0_scan[i]:
                pygame.draw.rect(self._surface, DebuggerColors.SPRITE_P0, (px, y+6, scale-1, 8))

    def _draw_tia_view(self):
        """Draw TIA register state"""
        stella = self.atari.stella
        y = 50

        title_surf = self._font.render("TIA REGISTERS", True, DebuggerColors.TITLE)
        self._surface.blit(title_surf, (self.PANEL_PADDING, y))
        y += 30

        # Color registers panel
        panel_rect = (self.PANEL_PADDING, y, 380, 120)
        pygame.draw.rect(self._surface, DebuggerColors.PANEL_BG, panel_rect)
        pygame.draw.rect(self._surface, DebuggerColors.BORDER, panel_rect, 1)

        title_surf = self._small_font.render("COLOR REGISTERS", True, DebuggerColors.TITLE)
        self._surface.blit(title_surf, (20, y + 5))

        colors = [
            ("COLUP0", stella.nextLine.pColor[0]),
            ("COLUP1", stella.nextLine.pColor[1]),
            ("COLUPF", stella.nextLine.playfieldColor),
            ("COLUBK", stella.nextLine.backgroundColor),
        ]

        col_y = y + 25
        for name, color_val in colors:
            name_surf = self._small_font.render(f"{name}:", True, DebuggerColors.REGISTER_NAME)
            self._surface.blit(name_surf, (20, col_y))

            # Color swatch
            pygame.draw.rect(self._surface, self._int_to_rgb(color_val), (100, col_y, 30, 14))
            pygame.draw.rect(self._surface, DebuggerColors.BORDER, (100, col_y, 30, 14), 1)

            # Hex value
            val_surf = self._small_font.render(f"${color_val:06X}", True, DebuggerColors.VALUE)
            self._surface.blit(val_surf, (140, col_y))

            col_y += 20

        # Collision registers panel
        y += 140
        panel_rect = (self.PANEL_PADDING, y, 380, 180)
        pygame.draw.rect(self._surface, DebuggerColors.PANEL_BG, panel_rect)
        pygame.draw.rect(self._surface, DebuggerColors.BORDER, panel_rect, 1)

        title_surf = self._small_font.render("COLLISION REGISTERS", True, DebuggerColors.TITLE)
        self._surface.blit(title_surf, (20, y + 5))

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

        col_y = y + 25
        for name, val, desc in collisions:
            name_surf = self._small_font.render(f"{name}:", True, DebuggerColors.REGISTER_NAME)
            self._surface.blit(name_surf, (20, col_y))

            val_surf = self._small_font.render(f"${val:02X}", True,
                                               DebuggerColors.CHANGED if val else DebuggerColors.VALUE)
            self._surface.blit(val_surf, (80, col_y))

            desc_surf = self._small_font.render(desc, True, DebuggerColors.TEXT)
            self._surface.blit(desc_surf, (130, col_y))

            col_y += 18

        # Horizontal motion panel
        y += 200
        panel_rect = (self.PANEL_PADDING, y, 380, 100)
        pygame.draw.rect(self._surface, DebuggerColors.PANEL_BG, panel_rect)
        pygame.draw.rect(self._surface, DebuggerColors.BORDER, panel_rect, 1)

        title_surf = self._small_font.render("HORIZONTAL MOTION", True, DebuggerColors.TITLE)
        self._surface.blit(title_surf, (20, y + 5))

        hm = stella.nextLine
        motions = [
            ("HMP0", hm.hmp[0]),
            ("HMP1", hm.hmp[1]),
            ("HMM0", hm.hmm[0]),
            ("HMM1", hm.hmm[1]),
            ("HMBL", hm.hmbl),
        ]

        col_y = y + 25
        col_x = 20
        for name, val in motions:
            name_surf = self._small_font.render(f"{name}: ${val:02X}", True, DebuggerColors.TEXT)
            self._surface.blit(name_surf, (col_x, col_y))
            col_x += 75
            if col_x > 300:
                col_x = 20
                col_y += 18

        # Right side - RIOT/Timer info
        x = 410
        y = 80

        panel_rect = (x, y, 370, 150)
        pygame.draw.rect(self._surface, DebuggerColors.PANEL_BG, panel_rect)
        pygame.draw.rect(self._surface, DebuggerColors.BORDER, panel_rect, 1)

        title_surf = self._small_font.render("RIOT / TIMER", True, DebuggerColors.TITLE)
        self._surface.blit(title_surf, (x + 10, y + 5))

        riot = self.atari.riot
        info = [
            f"Timer Interval: {riot.interval}x",
            f"Set Time: {riot.set_time}",
            f"Expiration: {riot.expiration_time}",
            f"Current Clock: {self.atari.clocks.system_clock}",
        ]

        info_y = y + 30
        for line in info:
            line_surf = self._small_font.render(line, True, DebuggerColors.TEXT)
            self._surface.blit(line_surf, (x + 10, info_y))
            info_y += 20

        # Input state
        y = 250
        panel_rect = (x, y, 370, 100)
        pygame.draw.rect(self._surface, DebuggerColors.PANEL_BG, panel_rect)
        pygame.draw.rect(self._surface, DebuggerColors.BORDER, panel_rect, 1)

        title_surf = self._small_font.render("INPUT STATE", True, DebuggerColors.TITLE)
        self._surface.blit(title_surf, (x + 10, y + 5))

        inputs = self.atari.inputs
        swcha = inputs.swcha
        swchb = inputs.swchb

        # Decode joystick
        joy_info = []
        if not (swcha & 0x10): joy_info.append("UP")
        if not (swcha & 0x20): joy_info.append("DOWN")
        if not (swcha & 0x40): joy_info.append("LEFT")
        if not (swcha & 0x80): joy_info.append("RIGHT")
        if not (inputs.input7 & 0x80): joy_info.append("FIRE")

        info = [
            f"SWCHA: ${swcha:02X} ({', '.join(joy_info) if joy_info else 'none'})",
            f"SWCHB: ${swchb:02X}",
            f"SELECT: {'ON' if not (swchb & 0x1) else 'off'}  "
            f"RESET: {'ON' if not (swchb & 0x2) else 'off'}",
        ]

        info_y = y + 30
        for line in info:
            line_surf = self._small_font.render(line, True, DebuggerColors.TEXT)
            self._surface.blit(line_surf, (x + 10, info_y))
            info_y += 20

    def _int_to_rgb(self, color_int):
        """Convert packed RGB integer to tuple"""
        r = (color_int >> 16) & 0xFF
        g = (color_int >> 8) & 0xFF
        b = color_int & 0xFF
        return (r, g, b)

    def step(self):
        """Called each frame to update debugger state"""
        if not self.active:
            return

        # Update state capture periodically (every frame when not paused)
        if not self.paused:
            self._capture_state()
