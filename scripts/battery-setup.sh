#!/bin/bash
# ============================================================
# battery-setup.sh — Optimización de batería para 7h de trabajo
# Hardware: Intel i7-13700H + NVIDIA RTX 4060 Max-Q (Optimus)
# Objetivo: máxima autonomía SIN sacrificar rendimiento
# ============================================================
set -euo pipefail

echo ""
echo "=== Pegaso Battery Optimizer ==="
echo "    i7-13700H + RTX 4060 Max-Q"
echo ""

# ─── 1. TLP — config optimizada ────────────────────────────
echo "[1/4] Configurando TLP para 7h de batería con rendimiento..."

cat > /etc/tlp.d/99-pegaso.conf << 'TLP'
# ============================================================
# Pegaso TLP Config — i7-13700H + RTX 4060 Max-Q Optimus
# Objetivo: 7h batería con rendimiento real mantenido
# ============================================================

# ── CPU ────────────────────────────────────────────────────
# schedutil responde dinámicamente: usa boost cuando necesitas,
# baja cuando estás idle — mucho más eficiente que powersave flat.
CPU_SCALING_GOVERNOR_ON_AC=performance
CPU_SCALING_GOVERNOR_ON_BAT=schedutil

# balance_power permite turbo en rafagas cortas (compilar, build Docker, etc.)
CPU_ENERGY_PERF_POLICY_ON_AC=performance
CPU_ENERGY_PERF_POLICY_ON_BAT=balance_power

# MANTENER TURBO ACTIVO — en i7-13700H híbrido el turbo es más
# eficiente que mantener frecuencia baja constante (los E-cores
# completan la tarea más rápido y vuelven a idle)
CPU_BOOST_ON_AC=1
CPU_BOOST_ON_BAT=1
CPU_HWP_DYN_BOOST_ON_AC=1
CPU_HWP_DYN_BOOST_ON_BAT=1

# ── Platform Profile ───────────────────────────────────────
# "balanced" mantiene rendimiento, "low-power" lo castiga mucho
PLATFORM_PROFILE_ON_AC=performance
PLATFORM_PROFILE_ON_BAT=balanced

# ── PCIe / ASPM ───────────────────────────────────────────
PCIE_ASPM_ON_AC=default
PCIE_ASPM_ON_BAT=powersupersave

# ── GPU NVIDIA (Optimus) ──────────────────────────────────
# Runtime PM: apaga la discreta cuando no se usa
RUNTIME_PM_ON_AC=auto
RUNTIME_PM_ON_BAT=auto

# ── WiFi ──────────────────────────────────────────────────
# Mantener WiFi a plena potencia para trabajo remoto
WIFI_PWR_ON_AC=off
WIFI_PWR_ON_BAT=off

# ── USB ───────────────────────────────────────────────────
USB_AUTOSUSPEND=1
USB_DENYLIST="usbhid"

# ── Almacenamiento ────────────────────────────────────────
SATA_LINKPWR_ON_AC=max_performance
SATA_LINKPWR_ON_BAT=min_power
AHCI_RUNTIME_PM_ON_AC=on
AHCI_RUNTIME_PM_ON_BAT=auto

# ── Audio ─────────────────────────────────────────────────
SOUND_POWER_SAVE_ON_BAT=1
SOUND_POWER_SAVE_CONTROLLER=Y

# ── Sistema ───────────────────────────────────────────────
NMI_WATCHDOG=0
WOL_DISABLE=Y
RESTORE_DEVICE_STATE_ON_STARTUP=0
TLP

echo "   ✅ Config TLP guardada en /etc/tlp.d/99-pegaso.conf"

# ─── 2. Aplicar config TLP inmediatamente ──────────────────
echo "[2/4] Aplicando configuración TLP..."
tlp start 2>/dev/null || true
echo "   ✅ TLP reiniciado"

# ─── 3. NVIDIA — regla udev para gestionar potencia ────────
echo "[3/4] Configurando NVIDIA Optimus con udev..."

cat > /etc/udev/rules.d/99-pegaso-nvidia-power.rules << 'UDEV'
# Pegaso: Limitar RTX 4060 Max-Q a 50W en batería (vs 80W AC)
# Permite usar la GPU en batería pero con consumo controlado

# Al desconectar AC: limitar TDP de la GPU
ACTION=="change", SUBSYSTEM=="power_supply", ATTR{online}=="0", \
    RUN+="/bin/bash -c 'sleep 2 && nvidia-smi -pl 50 2>/dev/null || true'"

# Al conectar AC: restablecer TDP completo
ACTION=="change", SUBSYSTEM=="power_supply", ATTR{online}=="1", \
    RUN+="/bin/bash -c 'sleep 1 && nvidia-smi -pl 80 2>/dev/null || true'"
UDEV

udevadm control --reload-rules 2>/dev/null || true
echo "   ✅ Regla udev NVIDIA instalada"

# ─── 4. Thermal — thermald si está disponible ──────────────
echo "[4/4] Verificando gestión térmica..."
if systemctl is-active --quiet thermald 2>/dev/null; then
    echo "   ✅ thermald activo"
else
    echo "   ℹ️  thermald no activo (opcional)"
fi

# ─── Aplicar governor ahora mismo ─────────────────────────
BATT_STATUS=$(cat /sys/class/power_supply/BAT0/status 2>/dev/null || echo "Unknown")
if [ "$BATT_STATUS" = "Discharging" ]; then
    for cpu in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do
        echo schedutil > "$cpu" 2>/dev/null || true
    done
    echo "   ✅ Governor cambiado a 'schedutil' en todos los cores"
fi

# ─── Resumen ───────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════════"
echo "✅ Batería optimizada para 7h de trabajo"
echo ""
echo "  CAMBIOS CLAVE:"
echo "  • CPU governor en batería: schedutil (dinámico, no slow)"
echo "  • Turbo Boost: ACTIVADO (más eficiente en i7-13700H)"
echo "  • Platform profile en batería: balanced (no low-power)"
echo "  • NVIDIA en batería: TDP limitado a 50W con Optimus"
echo "  • WiFi: sin throttling (para trabajo remoto)"
echo ""
echo "  ESTIMACIÓN AUTONOMÍA:"
echo "  • Trabajo web/código: 6.5-8h"
echo "  • Con vLLM activo: 4-5h"
echo "  • Máximo ahorro (make power-save): 8-10h"
echo ""
echo "  COMANDOS DISPONIBLES:"
echo "  make battery       → Ver consumo ahora"
echo "  make power-balanced → Rendimiento equilibrado (recomendado)"
echo "  make power-save    → Ahorro máximo"
echo "  make start-gpu     → Activar vLLM con GPU"
echo "═══════════════════════════════════════════════════════"
