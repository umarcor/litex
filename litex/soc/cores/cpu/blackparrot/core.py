# BlackParrot Chip core support for the LiteX SoC.
#
# Authors: Sadullah Canakci & Cansu Demirkiran  <{scanakci,cansu}@bu.edu>
# Copyright (c) 2019, Boston University
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:
#
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#
#     * Redistributions in binary form must reproduce the above
#       copyright notice, this list of conditions and the following
#       disclaimer in the documentation and/or other materials provided
#       with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import os
import sys
from migen import *

from litex import get_data_mod
from litex.soc.interconnect import axi
from litex.soc.interconnect import wishbone
from litex.soc.cores.cpu import CPU, CPU_GCC_TRIPLE_RISCV64

CPU_VARIANTS = ["standard", "sim"]

GCC_FLAGS = {
    "standard": "-march=rv64ima -mabi=lp64 ",
    "sim":      "-march=rv64ima -mabi=lp64 ",
}

class BlackParrotRV64(CPU):
    name                 = "blackparrot"
    human_name           = "BlackParrotRV64[ima]"
    variants             = CPU_VARIANTS
    data_width           = 64
    endianness           = "little"
    gcc_triple           = CPU_GCC_TRIPLE_RISCV64
    linker_output_format = "elf64-littleriscv"
    nop                  = "nop"
    io_regions           = {0x50000000: 0x10000000} # origin, length

    @property
    def mem_map(self):
        return {
            "csr"      : 0x50000000,
            "rom"      : 0x70000000,
            "sram"     : 0x71000000,
            "main_ram" : 0x80000000,
        }

    @property
    def gcc_flags(self):
        flags =  "-mno-save-restore "
        flags += GCC_FLAGS[self.variant]
        flags += "-D__blackparrot__ "
        return flags

    def __init__(self, platform, variant="standard"):
        self.platform     = platform
        self.variant      = variant
        self.reset        = Signal()
        self.idbus        = idbus = wishbone.Interface(data_width=64, adr_width=37)
        self.periph_buses = [idbus]
        self.memory_buses = []

        self.cpu_params = dict(
            # Clock / Reset
            i_clk_i   = ClockSignal(),
            i_reset_i = ResetSignal() | self.reset,

            # Wishbone (I/D)
            i_wbm_dat_i  = idbus.dat_r,
            o_wbm_dat_o  = idbus.dat_w,
            i_wbm_ack_i  = idbus.ack,
            i_wbm_err_i  = idbus.err,
            o_wbm_adr_o  = idbus.adr,
            o_wbm_stb_o  = idbus.stb,
            o_wbm_cyc_o  = idbus.cyc,
            o_wbm_sel_o  = idbus.sel,
            o_wbm_we_o   = idbus.we,
            o_wbm_cti_o  = idbus.cti,
            o_wbm_bte_o  = idbus.bte,
        )

        # Prepare verilog sources
        self.prepare_sources(platform)

        # Add verilog sources
        self.add_sources(platform)

    def set_reset_address(self, reset_address):
        assert not hasattr(self, "reset_address")
        self.reset_address = reset_address
        assert reset_address == 0x70000000, "cpu_reset_addr hardcoded to 0x70000000!"

    @staticmethod
    def prepare_sources(platform):
        sdir = get_data_mod("cpu", "blackparrot").data_location
        cdir = os.path.dirname(__file__)
        bp_common_dir = os.path.join(sdir, "bp_common")
        bp_me_dir     = os.path.join(sdir, "bp_me")
        bp_top_dir    = os.path.join(sdir, "bp_top")
        os.system(f"sed -i \"s/localparam dram_base_addr_gp         = 40'h00_8000_0000;/localparam dram_base_addr_gp         = 40'h00_7000_0000;/\" {bp_common_dir}/src/include/bp_common_pkg.vh")
        os.system(f"sed -i \"s/localparam bp_pc_entry_point_gp=39'h00_8000_0000/localparam bp_pc_entry_point_gp=39'h00_7000_0000/\" {bp_me_dir}/test/common/bp_cce_mmio_cfg_loader.v")
        os.system(f"sed -i \"s/wire local_cmd_li        = (cmd_fifo_selected_lo.header.addr < dram_base_addr_gp);/wire local_cmd_li        = (cmd_fifo_selected_lo.header.addr < 32'h5000_0000);/\" {bp_top_dir}/src/v/bp_softcore.v")
        os.system(f"cp {cdir}/cce_ucode.mem /tmp/.")

    @staticmethod
    def add_sources(platform):
        sdir = get_data_mod("cpu", "blackparrot").data_location
        cdir = os.path.dirname(__file__)
        bp_paths = [
            "external/basejump_stl/bsg_dataflow",
            "external/basejump_stl/bsg_mem",
            "external/basejump_stl/bsg_misc",
            "external/basejump_stl/bsg_test",
            "external/basejump_stl/bsg_noc",
            "bp_common/src/include",
            "bp_fe/src/include",
            "bp_be/src/include",
            "bp_be/src/include/bp_be_dcache",
            "bp_me/src/include/v",
            "bp_top/src/include",
        ]
        for path in bp_paths:
            platform.add_verilog_include_path(os.path.join(sdir, path))
        bp_sources = [
            # bp_common
            "bp_common/src/include/bp_common_rv64_pkg.vh",
            "bp_common/src/include/bp_common_pkg.vh",
            "bp_common/src/include/bp_common_aviary_pkg.vh",
            "bp_common/src/include/bp_common_cfg_link_pkg.vh",

            # bp_fe
            "bp_fe/src/include/bp_fe_icache_pkg.vh",
            "bp_fe/src/include/bp_fe_pkg.vh",
            "bp_be/src/include/bp_be_pkg.vh",
            "bp_be/src/include/bp_be_dcache/bp_be_dcache_pkg.vh",
            "bp_me/src/include/v/bp_me_pkg.vh",
            "bp_me/src/include/v/bp_cce_pkg.v",

            # basejump_stl
            "external/basejump_stl/bsg_cache/bsg_cache_pkg.v",
            "external/basejump_stl/bsg_noc/bsg_noc_pkg.v",
            "external/basejump_stl/bsg_noc/bsg_wormhole_router_pkg.v",

            "external/basejump_stl/bsg_fsb/bsg_fsb_node_trace_replay.v",

            "external/basejump_stl/bsg_async/bsg_async_fifo.v",
            "external/basejump_stl/bsg_async/bsg_launch_sync_sync.v",
            "external/basejump_stl/bsg_async/bsg_async_ptr_gray.v",
            "external/basejump_stl/bsg_cache/bsg_cache.v",
            "external/basejump_stl/bsg_cache/bsg_cache_dma.v",
            "external/basejump_stl/bsg_cache/bsg_cache_miss.v",
            "external/basejump_stl/bsg_cache/bsg_cache_decode.v",
            "external/basejump_stl/bsg_cache/bsg_cache_sbuf.v",
            "external/basejump_stl/bsg_cache/bsg_cache_sbuf_queue.v",

            "external/basejump_stl/bsg_dataflow/bsg_channel_tunnel.v",
            "external/basejump_stl/bsg_dataflow/bsg_channel_tunnel_in.v",
            "external/basejump_stl/bsg_dataflow/bsg_channel_tunnel_out.v",
            "external/basejump_stl/bsg_dataflow/bsg_1_to_n_tagged_fifo.v",
            "external/basejump_stl/bsg_dataflow/bsg_1_to_n_tagged.v",
            "external/basejump_stl/bsg_dataflow/bsg_fifo_1r1w_large.v",
            "external/basejump_stl/bsg_dataflow/bsg_fifo_1r1w_pseudo_large.v",
            "external/basejump_stl/bsg_dataflow/bsg_fifo_1r1w_small.v",
            "external/basejump_stl/bsg_dataflow/bsg_fifo_1r1w_small_unhardened.v",
            "external/basejump_stl/bsg_dataflow/bsg_fifo_1rw_large.v",
            "external/basejump_stl/bsg_dataflow/bsg_fifo_tracker.v",
            "external/basejump_stl/bsg_dataflow/bsg_flow_counter.v",
            "external/basejump_stl/bsg_dataflow/bsg_one_fifo.v",
            "external/basejump_stl/bsg_dataflow/bsg_parallel_in_serial_out.v",
            "external/basejump_stl/bsg_dataflow/bsg_parallel_in_serial_out_dynamic.v",
            "external/basejump_stl/bsg_dataflow/bsg_round_robin_1_to_n.v",
            "external/basejump_stl/bsg_dataflow/bsg_round_robin_2_to_2.v",
            "external/basejump_stl/bsg_dataflow/bsg_round_robin_n_to_1.v",
            "external/basejump_stl/bsg_dataflow/bsg_serial_in_parallel_out.v",
            "external/basejump_stl/bsg_dataflow/bsg_serial_in_parallel_out_dynamic.v",
            "external/basejump_stl/bsg_dataflow/bsg_serial_in_parallel_out_full.v",
            "external/basejump_stl/bsg_dataflow/bsg_shift_reg.v",
            "external/basejump_stl/bsg_dataflow/bsg_two_fifo.v",

            "external/basejump_stl/bsg_mem/bsg_cam_1r1w.v",
            "external/basejump_stl/bsg_mem/bsg_mem_1r1w.v",
            "external/basejump_stl/bsg_mem/bsg_mem_1r1w_sync.v",
            "external/basejump_stl/bsg_mem/bsg_mem_1r1w_sync_synth.v",
            "external/basejump_stl/bsg_mem/bsg_mem_1r1w_synth.v",
            "external/basejump_stl/bsg_mem/bsg_mem_1rw_sync.v",
            "external/basejump_stl/bsg_mem/bsg_mem_1rw_sync_mask_write_bit_synth.v",
            "external/basejump_stl/bsg_mem/bsg_mem_1rw_sync_mask_write_byte.v",
            "external/basejump_stl/bsg_mem/bsg_mem_1rw_sync_mask_write_byte_synth.v",
            "external/basejump_stl/bsg_mem/bsg_mem_1rw_sync_synth.v",
            "external/basejump_stl/bsg_mem/bsg_mem_2r1w_sync.v",
            "external/basejump_stl/bsg_mem/bsg_mem_2r1w_sync_synth.v",

            "external/basejump_stl/bsg_misc/bsg_adder_cin.v",
            "external/basejump_stl/bsg_misc/bsg_adder_ripple_carry.v",
            "external/basejump_stl/bsg_misc/bsg_arb_fixed.v",
            "external/basejump_stl/bsg_misc/bsg_array_concentrate_static.v",
            "external/basejump_stl/bsg_misc/bsg_buf.v",
            "external/basejump_stl/bsg_misc/bsg_buf_ctrl.v",
            "external/basejump_stl/bsg_misc/bsg_circular_ptr.v",
            "external/basejump_stl/bsg_misc/bsg_concentrate_static.v",
            "external/basejump_stl/bsg_misc/bsg_counter_clear_up.v",
            "external/basejump_stl/bsg_misc/bsg_counter_set_down.v",
            "external/basejump_stl/bsg_misc/bsg_counter_set_en.v",
            "external/basejump_stl/bsg_misc/bsg_counter_up_down.v",
            "external/basejump_stl/bsg_misc/bsg_counter_up_down_variable.v",
            "external/basejump_stl/bsg_misc/bsg_crossbar_o_by_i.v",
            "external/basejump_stl/bsg_misc/bsg_cycle_counter.v",
            "external/basejump_stl/bsg_misc/bsg_decode.v",
            "external/basejump_stl/bsg_misc/bsg_decode_with_v.v",
            "external/basejump_stl/bsg_misc/bsg_dff.v",
            "external/basejump_stl/bsg_misc/bsg_dff_en_bypass.v",
            "external/basejump_stl/bsg_misc/bsg_dff_reset_en_bypass.v",
            "external/basejump_stl/bsg_misc/bsg_dff_chain.v",
            "external/basejump_stl/bsg_misc/bsg_dff_en.v",
            "external/basejump_stl/bsg_misc/bsg_dff_reset.v",
            "external/basejump_stl/bsg_misc/bsg_dff_reset_en.v",
            "external/basejump_stl/bsg_misc/bsg_edge_detect.v",
            "external/basejump_stl/bsg_misc/bsg_encode_one_hot.v",
            "external/basejump_stl/bsg_misc/bsg_expand_bitmask.v",
            "external/basejump_stl/bsg_misc/bsg_hash_bank.v",
            "external/basejump_stl/bsg_misc/bsg_hash_bank_reverse.v",
            "external/basejump_stl/bsg_misc/bsg_idiv_iterative.v",
            "external/basejump_stl/bsg_misc/bsg_idiv_iterative_controller.v",
            "external/basejump_stl/bsg_misc/bsg_lfsr.v",
            "external/basejump_stl/bsg_misc/bsg_lru_pseudo_tree_decode.v",
            "external/basejump_stl/bsg_misc/bsg_lru_pseudo_tree_encode.v",
            "external/basejump_stl/bsg_misc/bsg_mux.v",
            "external/basejump_stl/bsg_misc/bsg_mux_butterfly.v",
            "external/basejump_stl/bsg_misc/bsg_mux_one_hot.v",
            "external/basejump_stl/bsg_misc/bsg_mux_segmented.v",
            "external/basejump_stl/bsg_misc/bsg_muxi2_gatestack.v",
            "external/basejump_stl/bsg_misc/bsg_nor2.v",
            "external/basejump_stl/bsg_misc/bsg_nor3.v",
            "external/basejump_stl/bsg_misc/bsg_nand.v",
            "external/basejump_stl/bsg_misc/bsg_priority_encode.v",
            "external/basejump_stl/bsg_misc/bsg_priority_encode_one_hot_out.v",
            "external/basejump_stl/bsg_misc/bsg_reduce.v",
            "external/basejump_stl/bsg_misc/bsg_reduce_segmented.v",
            "external/basejump_stl/bsg_misc/bsg_round_robin_arb.v",
            "external/basejump_stl/bsg_misc/bsg_scan.v",
            "external/basejump_stl/bsg_misc/bsg_strobe.v",
            "external/basejump_stl/bsg_misc/bsg_swap.v",
            "external/basejump_stl/bsg_misc/bsg_thermometer_count.v",
            "external/basejump_stl/bsg_misc/bsg_transpose.v",
            "external/basejump_stl/bsg_misc/bsg_unconcentrate_static.v",
            "external/basejump_stl/bsg_misc/bsg_xnor.v",

            "external/basejump_stl/bsg_noc/bsg_mesh_stitch.v",
            "external/basejump_stl/bsg_noc/bsg_noc_repeater_node.v",
            "external/basejump_stl/bsg_noc/bsg_wormhole_concentrator.v",
            "external/basejump_stl/bsg_noc/bsg_wormhole_concentrator_in.v",
            "external/basejump_stl/bsg_noc/bsg_wormhole_concentrator_out.v",
            "external/basejump_stl/bsg_noc/bsg_wormhole_router.v",
            "external/basejump_stl/bsg_noc/bsg_wormhole_router_adapter.v",
            "external/basejump_stl/bsg_noc/bsg_wormhole_router_adapter_in.v",
            "external/basejump_stl/bsg_noc/bsg_wormhole_router_adapter_out.v",
            "external/basejump_stl/bsg_noc/bsg_wormhole_router_decoder_dor.v",
            "external/basejump_stl/bsg_noc/bsg_wormhole_router_input_control.v  ",
            "external/basejump_stl/bsg_noc/bsg_wormhole_router_output_control.v ",

            # bp_common
            "bp_common/src/v/bsg_fifo_1r1w_rolly.v",
            "bp_common/src/v/bp_pma.v",
            "bp_common/src/v/bp_tlb.v",
            "bp_common/src/v/bp_tlb_replacement.v",

            # bp_be
            "bp_be/src/v/bp_be_top.v",
            "bp_be/src/v/bp_be_calculator/bp_be_bypass.v",
            "bp_be/src/v/bp_be_calculator/bp_be_calculator_top.v",
            "bp_be/src/v/bp_be_calculator/bp_be_instr_decoder.v",
            "bp_be/src/v/bp_be_calculator/bp_be_int_alu.v",
            "bp_be/src/v/bp_be_calculator/bp_be_pipe_fp.v",
            "bp_be/src/v/bp_be_calculator/bp_be_pipe_int.v",
            "bp_be/src/v/bp_be_calculator/bp_be_pipe_ctrl.v",
            "bp_be/src/v/bp_be_calculator/bp_be_pipe_long.v",
            "bp_be/src/v/bp_be_calculator/bp_be_pipe_mem.v",
            "bp_be/src/v/bp_be_calculator/bp_be_pipe_mul.v",
            "bp_be/src/v/bp_be_calculator/bp_be_regfile.v",
            "bp_be/src/v/bp_be_checker/bp_be_checker_top.v",
            "bp_be/src/v/bp_be_checker/bp_be_detector.v",
            "bp_be/src/v/bp_be_checker/bp_be_director.v",
            "bp_be/src/v/bp_be_checker/bp_be_scheduler.v",
            "bp_be/src/v/bp_be_mem/bp_be_ptw.v",
            "bp_be/src/v/bp_be_mem/bp_be_csr.v",
            "bp_be/src/v/bp_be_mem/bp_be_dcache/bp_be_dcache.v",
            "bp_be/src/v/bp_be_mem/bp_be_dcache/bp_be_dcache_lce_cmd.v",
            "bp_be/src/v/bp_be_mem/bp_be_dcache/bp_be_dcache_lce.v",
            "bp_be/src/v/bp_be_mem/bp_be_dcache/bp_be_dcache_lce_req.v",
            "bp_be/src/v/bp_be_mem/bp_be_dcache/bp_be_dcache_wbuf.v",
            "bp_be/src/v/bp_be_mem/bp_be_dcache/bp_be_dcache_wbuf_queue.v",
            "bp_be/src/v/bp_be_mem/bp_be_mem_top.v",

            # bp_fe
            "bp_fe/src/v/bp_fe_bht.v",
            "bp_fe/src/v/bp_fe_btb.v",
            "bp_fe/src/v/bp_fe_lce_cmd.v",
            "bp_fe/src/v/bp_fe_icache.v",
            "bp_fe/src/v/bp_fe_instr_scan.v",
            "bp_fe/src/v/bp_fe_lce.v",
            "bp_fe/src/v/bp_fe_lce_req.v",
            "bp_fe/src/v/bp_fe_mem.v",
            "bp_fe/src/v/bp_fe_pc_gen.v",
            "bp_fe/src/v/bp_fe_top.v",

            # bp_me
            "bp_me/src/v/cache/bp_me_cache_dma_to_cce.v",
            "bp_me/src/v/cache/bp_me_cache_slice.v",
            "bp_me/src/v/cache/bp_me_cce_to_cache.v",
            "bp_me/src/v/cce/bp_cce.v",
            "bp_me/src/v/cce/bp_cce_alu.v",
            "bp_me/src/v/cce/bp_cce_arbitrate.v",
            "bp_me/src/v/cce/bp_cce_branch.v",
            "bp_me/src/v/cce/bp_cce_buffered.v",
            "bp_me/src/v/cce/bp_cce_dir.v",
            "bp_me/src/v/cce/bp_cce_dir_lru_extract.v",
            "bp_me/src/v/cce/bp_cce_dir_segment.v",
            "bp_me/src/v/cce/bp_cce_dir_tag_checker.v",
            "bp_me/src/v/cce/bp_cce_gad.v",
            "bp_me/src/v/cce/bp_cce_inst_decode.v",
            "bp_me/src/v/cce/bp_cce_inst_predecode.v",
            "bp_me/src/v/cce/bp_cce_inst_ram.v",
            "bp_me/src/v/cce/bp_cce_inst_stall.v",
            "bp_me/src/v/cce/bp_cce_msg.v",
            "bp_me/src/v/cce/bp_cce_pending_bits.v",
            "bp_me/src/v/cce/bp_cce_reg.v",
            "bp_me/src/v/cce/bp_cce_spec_bits.v",
            "bp_me/src/v/cce/bp_cce_src_sel.v",
            "bp_me/src/v/cce/bp_io_cce.v",
            "bp_me/src/v/cce/bp_cce_fsm.v",
            "bp_me/src/v/cce/bp_cce_wrapper.v",
            "bp_me/src/v/cce/bp_uce.v",
            "bp_me/src/v/wormhole/bp_me_addr_to_cce_id.v",
            "bp_me/src/v/wormhole/bp_me_cce_id_to_cord.v",
            "bp_me/src/v/wormhole/bp_me_cce_to_mem_link_bidir.v",
            "bp_me/src/v/wormhole/bp_me_cce_to_mem_link_client.v",
            "bp_me/src/v/wormhole/bp_me_cce_to_mem_link_master.v",
            "bp_me/src/v/wormhole/bp_me_cord_to_id.v",
            "bp_me/src/v/wormhole/bp_me_lce_id_to_cord.v",
            "bp_me/src/v/wormhole/bp_me_wormhole_packet_encode_lce_cmd.v",
            "bp_me/src/v/wormhole/bp_me_wormhole_packet_encode_lce_req.v",
            "bp_me/src/v/wormhole/bp_me_wormhole_packet_encode_lce_resp.v",
            "bp_me/src/v/wormhole/bp_me_wormhole_packet_encode_mem_cmd.v",
            "bp_me/src/v/wormhole/bp_me_wormhole_packet_encode_mem_resp.v",
            "bp_me/test/common/bp_cce_mmio_cfg_loader.v",

            # bp_top
            "bp_top/src/v/bp_nd_socket.v",
            "bp_top/src/v/bp_cacc_vdp.v",
            "bp_top/src/v/bp_cacc_tile.v",
            "bp_top/src/v/bp_cacc_tile_node.v",
            "bp_top/src/v/bp_cacc_complex.v",
            "bp_top/src/v/bp_sacc_vdp.v",
            "bp_top/src/v/bp_sacc_tile.v",
            "bp_top/src/v/bp_sacc_tile_node.v",
            "bp_top/src/v/bp_sacc_complex.v",
            "bp_top/src/v/bp_cfg.v",
            "bp_top/src/v/bp_core.v",
            "bp_top/src/v/bp_core_complex.v",
            "bp_top/src/v/bp_core_minimal.v",
            "bp_top/src/v/bp_clint_node.v",
            "bp_top/src/v/bp_clint_slice.v",
            "bp_top/src/v/bp_l2e_tile.v",
            "bp_top/src/v/bp_l2e_tile_node.v",
            "bp_top/src/v/bp_io_complex.v",
            "bp_top/src/v/bp_io_link_to_lce.v",
            "bp_top/src/v/bp_io_tile.v",
            "bp_top/src/v/bp_io_tile_node.v",
            "bp_top/src/v/bp_mem_complex.v",
            "bp_top/src/v/bp_processor.v",
            "bp_top/src/v/bp_softcore.v",
            "bp_top/src/v/bp_tile.v",
            "bp_top/src/v/bp_tile_node.v",
            "bp_top/src/v/bsg_async_noc_link.v",
            "bp_top/test/common/bp_nonsynth_nbf_loader.v",
        ]
        for source in bp_sources:
            platform.add_source(os.path.join(sdir, source), "systemverilog")

        bp_litex_sources = [
            "bp_litex/bsg_mem_1rw_sync_mask_write_bit.v",
            "bp_litex/bp2wb_convertor.v",
            "bp_litex/ExampleBlackParrotSystem.v",
        ]
        for source in bp_litex_sources:
            platform.add_source(os.path.join(cdir, source), "systemverilog")

    def do_finalize(self):
        assert hasattr(self, "reset_address")
        self.specials += Instance("ExampleBlackParrotSystem", **self.cpu_params)
