#!/usr/bin/env python3
"""Static cross-check of the SystemVerilog test drafts in tests/ against the upstream source.

No HDL tool is needed. The script does what a compiler's elaboration would catch first:
  1. Unit tests: every named port / parameter in the DUT instantiation exists in the
     module header, every input port of the module is connected, and every internal
     signal probed as dut.<name> is declared in the module.
  2. System tests: every testbench task, constant and variable the drafts use is declared
     in nv_hsb_ip_simple_tb, task argument counts match, and every hierarchical path
     u_dut.<...> resolves instance by instance (or signal) in the RTL, including the
     `ifdef that must be defined for it to exist.

It does not check SystemVerilog syntax or timing. Usage:
  python3 tools/check_tests.py <path-to-holoscan-sensor-bridge>
Exit code 1 if anything does not resolve.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FAILS = []


def report(ok, name, detail=""):
    tag = "PASS" if ok else "FAIL"
    if not ok:
        FAILS.append(name)
    print(f"[{tag}] {name}" + (f"\n        {detail}" if detail else ""))


def strip_comments(text):
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"//[^\n]*", "", text)


def module_header(src, name):
    """Return (params, ports{name: dir}) from an ANSI module header."""
    text = strip_comments(src)
    m = re.search(r"\bmodule\s+" + name + r"\b(.*?)\)\s*;", text, flags=re.S)
    assert m, f"module {name} not found"
    head = m.group(1)
    params, ports = set(), {}
    pm = re.match(r"\s*(?:import[^;]*;\s*)*#\s*\((.*?)\)\s*\(", head, flags=re.S)
    if pm:
        for p in re.finditer(r"\b(?:parameter|localparam)\b[^,=]*?(\w+)\s*=", pm.group(1)):
            params.add(p.group(1))
        # parameters declared without the keyword after the first one
        for p in re.finditer(r",\s*(?:\w+\s+)?(?:\[[^\]]*\]\s*)?(\w+)\s*=", pm.group(1)):
            params.add(p.group(1))
        localp = set(re.findall(r"\blocalparam\b[^,=]*?(\w+)\s*=", pm.group(1)))
        params -= localp
        body = head[pm.end():]
    else:
        body = head[head.index("(") + 1:]
    cur = None
    for tok in re.split(r",", body):
        d = re.search(r"\b(input|output|inout)\b", tok)
        if d:
            cur = d.group(1)
        n = re.findall(r"(\w+)\s*(?:\[[^\]]*\]\s*)*$", tok.strip())
        if n and cur:
            ports[n[0]] = cur
    return params, ports


def instance_conns(tb, module):
    text = strip_comments(tb)
    m = re.search(r"\b" + module + r"\s*(#\s*\((.*?)\)\s*)?(\w+)\s*\((.*?)\)\s*;", text, flags=re.S)
    assert m, f"instance of {module} not found"
    params = set(re.findall(r"\.(\w+)\s*\(", m.group(2) or ""))
    conns = set(re.findall(r"\.(\w+)\b", m.group(4)))
    return m.group(3), params, conns


def declared(src, name):
    return re.search(r"\b(?:logic|reg|wire|bit|int|\w+_states|states|\w+_t)\b[^;]*\b" + name + r"\b",
                     strip_comments(src)) is not None


def check_unit(up):
    units = [
        ("tests/unit/tb_spi_turnaround.sv", "fpga/nv_hsb_ip/spi/spi.sv", "spi"),
        ("tests/unit/tb_uart_rx_rate.sv", "fpga/nv_hsb_ip/uart/uart.sv", "uart"),
        ("tests/unit/tb_i2s_clk_gen.sv", "fpga/nv_hsb_ip/ref_design/i2s/i2s_clk_gen.sv", "i2s_clk_gen"),
    ]
    for tbp, rtlp, mod in units:
        tb = (ROOT / tbp).read_text()
        rtl = (up / rtlp).read_text()
        params, ports = module_header(rtl, mod)
        inst, used_p, conns = instance_conns(tb, mod)
        bad_p = sorted(used_p - params)
        bad_c = sorted(conns - set(ports))
        missing_in = sorted(p for p, d in ports.items() if d == "input" and p not in conns)
        probes = sorted(set(re.findall(r"\b" + inst + r"\.(\w+)", strip_comments(tb))))
        bad_probe = [p for p in probes if not declared(rtl, p)]
        report(not (bad_p or bad_c or missing_in or bad_probe), f"{tbp}: {mod} instance",
               f"params used {sorted(used_p)}; unknown params {bad_p}; unknown ports {bad_c}; "
               f"unconnected inputs {missing_in}; internal probes {probes}, undeclared {bad_probe}")


def tb_sources(up):
    d = up / "fpga/nv_hsb_ip_simple_tb"
    return "\n".join(p.read_text() for p in sorted(d.rglob("*.sv*")))


def task_arity(tbsrc, name):
    m = re.search(r"\btask\s+(?:automatic\s+)?" + name + r"\s*\((.*?)\)\s*;", strip_comments(tbsrc), flags=re.S)
    if not m:
        return None
    return len([a for a in m.group(1).split(",") if a.strip()])


def call_arities(text, name):
    out = []
    for m in re.finditer(r"\b" + name + r"\s*\(", text):
        depth, i, args, cur = 1, m.end(), [], ""
        while depth:
            c = text[i]
            if c in "([{":
                depth += 1
            elif c in ")]}":
                depth -= 1
            if depth == 1 and c == ",":
                args.append(cur); cur = ""
            elif depth:
                cur += c
            i += 1
        args.append(cur)
        out.append(len([a for a in args if a.strip()]))
    if not out and re.search(r"\b" + name + r"\s*;", text):
        out.append(0)
    return out


# Hierarchical paths: (path, [(file, regex that must match, required `define or None)]).
HIER = {
    "u_dut": [("fpga/nv_hsb_ip_simple_tb/nv_hsb_ip_simple_tb.sv", r"HOLOLINK_top\s*#[\s\S]*?\)\s*u_dut\s*\(", None)],
    "u_dut.spi_ctrl_inst.state": [
        ("fpga/nv_hsb_ip/top/HOLOLINK_top.sv", r"spi_ctrl_fsm\s*#[\s\S]*?\)\s*spi_ctrl_inst\s*\(", None),
        ("fpga/nv_hsb_ip/spi/spi_ctrl_fsm.sv", r"spi_states\s+state\b", None)],
    "u_dut.gen_pack_inst[0].packetizer_top_inst.state": [
        ("fpga/nv_hsb_ip/top/HOLOLINK_top.sv", r"begin\s*:\s*gen_pack_inst[\s\S]*?\)\s*packetizer_top_inst\s*\(", "SENSOR_RX_IF_INST"),
        ("fpga/nv_hsb_ip/packetizer/packetizer_top.sv", r"\bstate\b\s*,|\bstate\s*;", None)],
    "u_dut.is_ptp_sync_msg": [("fpga/nv_hsb_ip/top/HOLOLINK_top.sv", r"logic\s*\[[^\]]*\]\s*is_ptp_sync_msg\s*;", None)],
    "u_dut.ack_axis_tvalid/tready/tlast": [
        ("fpga/nv_hsb_ip/top/HOLOLINK_top.sv", r"logic\s*\[[^\]]*\]\s*ack_axis_tvalid\s*;", None),
        ("fpga/nv_hsb_ip/top/HOLOLINK_top.sv", r"logic\s*\[[^\]]*\]\s*ack_axis_tready\s*;", None),
        ("fpga/nv_hsb_ip/top/HOLOLINK_top.sv", r"logic\s*\[[^\]]*\]\s*ack_axis_tlast\s*;", None),
        ("fpga/nv_hsb_ip/top/HOLOLINK_top.sv", r"`ifdef\s+SIF_TX_ROCE_RC_ENABLE\s*\n\s*\.ENABLE_ROCE_ACK\s*\(\s*1", "SIF_TX_ROCE_RC_ENABLE")],
    "u_dut.u_eeprom_info.eeprom_crc_err": [
        ("fpga/nv_hsb_ip/top/HOLOLINK_top.sv", r"`ifdef\s+ENUM_EEPROM\s*\n\s*eeprom_info\s*#[\s\S]*?\)\s*u_eeprom_info\s*\(", "ENUM_EEPROM"),
        ("fpga/nv_hsb_ip/sys_init/eeprom_info.sv", r"output\s+\w*\s*eeprom_crc_err", None)],
    "u_dut.u_eeprom_info.mac_addr": [
        ("fpga/nv_hsb_ip/sys_init/eeprom_info.sv", r"output\s+reg\s*\[47\s*:0\]\s*mac_addr", None)],
    "u_dut.host_pause_req": [
        ("fpga/nv_hsb_ip/top/HOLOLINK_top.sv", r"logic\s*\[[^\]]*\]\s*host_pause_req\s*;", "SENSOR_TX_IF_INST")],
    "u_dut.gen_pause[0].u_pause_gen.i_pause_time": [
        ("fpga/nv_hsb_ip/top/HOLOLINK_top.sv", r"begin\s*:\s*gen_pause\s*\n\s*pause_gen\s*#[\s\S]*?\)\s*u_pause_gen\s*\(", "SENSOR_TX_IF_INST"),
        ("fpga/nv_hsb_ip/sensor_tx/pause_gen.sv", r"input\s+(?:\w+\s+)?\[\s*15\s*:\s*0\s*\]\s*i_pause_time", None)],
    "u_dut.gen_rx_parser[0].rx_parser.u_axis_inp_buffer.in_pkt_cnt": [
        ("fpga/nv_hsb_ip/top/HOLOLINK_top.sv", r"begin\s*:\s*gen_rx_parser[\s\S]*?\)\s*rx_parser\s*\(", None),
        ("fpga/nv_hsb_ip/rx_parser/rx_parser.sv", r"axis_buffer\s*#[\s\S]*?\)\s*u_axis_inp_buffer\s*\(", None),
        ("fpga/nv_hsb_ip/lib_axis/axis_buffer.sv", r"logic\s*\[[^\]]*\]\s*in_pkt_cnt\s*;", None),
        ("fpga/nv_hsb_ip/lib_axis/axis_buffer.sv", r"logic\s*\[[^\]]*\]\s*out_pkt_cnt\s*;", None)],
    "u_dut.gen_pack_inst[0].packetizer_top_inst.o_axis_tvalid": [
        ("fpga/nv_hsb_ip/packetizer/packetizer_top.sv", r"output\s+(?:logic\s*)?\[[^\]]*\]\s*o_axis_tvalid\s*,", None),
        ("fpga/nv_hsb_ip/packetizer/packetizer_top.sv", r"output\s+(?:logic\s*)?\[[^\]]*\]\s*o_axis_tlast\s*,", None),
        ("fpga/nv_hsb_ip/packetizer/packetizer_top.sv", r"input\s+(?:logic\s*)?\[[^\]]*\]\s*i_axis_tready\s*[,)]", None)],
    "u_dut.u_eeprom_info.eeprom_dval": [
        ("fpga/nv_hsb_ip/sys_init/eeprom_info.sv", r"output\s+eeprom_dval", None)],
    "i_eeprom_model.eeprom_sda_drive": [
        ("fpga/nv_hsb_ip_simple_tb/eeprom_i2c_model.sv", r"logic\s+eeprom_sda_drive\s*;", None)],
    "i_eeprom_model.eeprom_memory": [
        ("fpga/nv_hsb_ip_simple_tb/nv_hsb_ip_simple_tb.sv", r"\)\s*i_eeprom_model\s*\(", None),
        ("fpga/nv_hsb_ip_simple_tb/eeprom_i2c_model.sv", r"logic\s*\[7:0\]\s*eeprom_memory\s*\[", None)],
}


def check_system(up):
    svh = ROOT / "tests/system/hsb_directed_tests.svh"
    text = strip_comments(svh.read_text())
    tb = tb_sources(up)
    # identifiers from the testbench that the drafts rely on
    names = ["build_ethernet_frame", "send_eth_packet", "ecb_write", "ecb_read",
             "program_packetizer_passthrough", "send_sensor_frame", "build_host2sen_send_frame",
             "DEFAULT_FPGA_MAC", "TB_HOST_MAC", "TB_FPGA_IP", "TB_HOST_IP", "ETH_UDP_CMD_PORT",
             "ecb_sequence_id", "hif_clk", "REG_PACK_CTRL_BASE", "REG_PACK_CTRL_STRIDE",
             "PACK_OFF_PACK_CFG", "PACK_CFG_LATENCY_LSB",
             # v7 tests
             "program_tx_strm_buff", "reg_tx_strm_buff", "TX_STRM_OFF_PAUSE_MAP", "TX_STRM_OFF_AFULL",
             "TX_STRM_OFF_AEMPTY", "TX_STRM_OFF_QUANTA", "TX_STRM_OFF_CTRL", "ROCE_OP_SEND_ONLY",
             "host2sen_psn", "hif_tx_sem", "i_sif_axis_tready", "i_sif_tx_clk", "o_sif_axis_tvalid",
             "o_sif_axis_tdata", "o_sif_axis_tkeep", "o_sif_axis_tlast", "i_hif_axis_tvalid",
             "i_hif_axis_tdata", "i_hif_axis_tkeep", "i_hif_axis_tlast", "i_hif_axis_tuser",
             "SIF_TX_WIDTH", "SIF_TX_BUF_SIZE",
             # v7.1 tests
             "SIF_RX_VP_COUNT", "SIF_RX_PACKETIZER_EN", "SIF_RX_WIDTH", "SIF_RX_VP_SIZE",
             "SIF_RX_SORT_RESOLUTION", "SIF_RX_NUM_CYCLES", "pack_vp_ram_index",
             "PACK_OFF_RAM_ADDR", "PACK_OFF_RAM_DATA", "REG_PACK_CTRL_BASE"]
    extra = re.findall(r"//\s*tb-names:\s*(.*)", svh.read_text())
    for line in extra:
        names += line.split()
    for n in names:
        if not re.search(r"\b" + n + r"\b", text):
            continue
        ok = re.search(r"\b(task|function)\s+(automatic\s+)?(\w+(\s*\[[^\]]*\])*\s+)?" + n + r"\b"
                       r"|\b(localparam|parameter|int|integer|logic|bit|semaphore)\b[^;]*\b" + n + r"\b"
                       r"|\bimport\s+HOLOLINK_pkg::" + n + r"\b", tb)
        report(ok is not None, f"tb name {n}")
    for t in ["build_ethernet_frame", "send_eth_packet", "ecb_write", "ecb_read",
              "program_packetizer_passthrough", "send_sensor_frame", "build_host2sen_send_frame",
              "program_tx_strm_buff"]:
        want = task_arity(tb, t)
        got = sorted(set(call_arities(text, t)))
        if got:
            report(got == [want], f"call arity {t}", f"declared {want}, used {got}")
    for path, rules in HIER.items():
        probe = path.split("/")[0]
        if not rules or not re.search(re.escape(probe).replace(r"\[0\]", r"\[\w+\]"), text):
            continue
        res = []
        for f, rx, need in rules:
            src = (up / f).read_text()
            res.append(re.search(rx, src) is not None)
        report(all(res), f"hierarchy {path}",
               "requires " + ", ".join(f"`define {n}" for _, _, n in rules if n) if any(n for _, _, n in rules) else "")


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    up = Path(sys.argv[1])
    check_unit(up)
    check_system(up)
    print("\nFAILED: " + (", ".join(FAILS) if FAILS else "none"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
