#!/usr/bin/env bash
# Para Fox nativo en el host
if pgrep -f "fox-binary serve" > /dev/null 2>&1; then
    pkill -f "fox-binary serve"
    echo "✅ Fox detenido."
else
    echo "Fox no estaba corriendo."
fi
