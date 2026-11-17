import React, { useEffect, useRef } from 'react';

/**
 * AgentAudioVisualizerAura
 * Ethereal, shader-driven organic glowing aura visualizer that reacts to
 * agent state ('idle' | 'listening' | 'thinking' | 'speaking') and audio amplitude.
 */
export function AgentAudioVisualizerAura({
  size = 'xl',
  color = '#1FD5F9',
  colorShift = 0.3,
  state = 'idle',
  themeMode = 'dark',
  audioLevel = 0.0,
  className = '',
  style = {},
}) {
  const canvasRef = useRef(null);
  const stateRef = useRef(state);
  const audioLevelRef = useRef(audioLevel);
  const animFrameRef = useRef(null);

  useEffect(() => {
    stateRef.current = state;
  }, [state]);

  useEffect(() => {
    audioLevelRef.current = audioLevel;
  }, [audioLevel]);

  // Size mapping
  const sizeMap = {
    icon: 48,
    sm: 96,
    md: 180,
    lg: 260,
    xl: 340,
  };
  const pixelSize = typeof size === 'number' ? size : sizeMap[size] || 320;

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    // Convert hex to rgb
    const hex = color.replace('#', '');
    const r = parseInt(hex.substring(0, 2), 16) / 255 || 0.12;
    const g = parseInt(hex.substring(2, 4), 16) / 255 || 0.84;
    const b = parseInt(hex.substring(4, 6), 16) / 255 || 0.98;

    let gl = null;
    try {
      gl = canvas.getContext('webgl', { alpha: true, antialias: true, premultipliedAlpha: false });
    } catch {
      gl = null;
    }

    if (!gl) {
      // Fallback: 2D Canvas Procedural Aura
      const ctx = canvas.getContext('2d');
      let t = 0;
      const render2D = () => {
        t += 0.03;
        const width = canvas.width;
        const height = canvas.height;
        ctx.clearRect(0, 0, width, height);

        const cx = width / 2;
        const cy = height / 2;
        const baseRadius = width * 0.22;
        const currState = stateRef.current;
        const currLevel = audioLevelRef.current;

        const pulse = Math.sin(t * (currState === 'speaking' ? 4 : currState === 'thinking' ? 6 : 2)) * 0.08;
        const radius = baseRadius * (1 + pulse + (currState === 'speaking' || currState === 'listening' ? currLevel * 0.5 : 0));

        // Outer glow
        const grad = ctx.createRadialGradient(cx, cy, radius * 0.2, cx, cy, radius * 1.8);
        grad.addColorStop(0, `rgba(${Math.round(r * 255)}, ${Math.round(g * 255)}, ${Math.round(b * 255)}, 0.85)`);
        grad.addColorStop(0.5, `rgba(${Math.round(r * 200)}, ${Math.round(g * 220)}, 255, 0.4)`);
        grad.addColorStop(0.8, `rgba(${Math.round(r * 150)}, ${Math.round(g * 180)}, 255, 0.15)`);
        grad.addColorStop(1, 'rgba(0, 0, 0, 0)');

        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.arc(cx, cy, radius * 1.8, 0, Math.PI * 2);
        ctx.fill();

        animFrameRef.current = requestAnimationFrame(render2D);
      };
      animFrameRef.current = requestAnimationFrame(render2D);
      return () => cancelAnimationFrame(animFrameRef.current);
    }

    // WebGL Shader Setup
    const vsSource = `
      attribute vec2 aPosition;
      void main() {
        gl_Position = vec4(aPosition, 0.0, 1.0);
      }
    `;

    const fsSource = `
      precision highp float;
      uniform vec2 iResolution;
      uniform float iTime;
      uniform vec3 uColor;
      uniform float uColorShift;
      uniform float uAudioLevel;
      uniform int uState; // 0=idle, 1=listening, 2=thinking, 3=speaking

      // Simplex-style noise approximation
      vec2 hash(vec2 p) {
        p = vec2(dot(p, vec2(127.1, 311.7)), dot(p, vec2(269.5, 183.3)));
        return -1.0 + 2.0 * fract(sin(p) * 43758.5453123);
      }

      float noise(vec2 p) {
        const float K1 = 0.366025404;
        const float K2 = 0.211324865;
        vec2 i = floor(p + (p.x + p.y) * K1);
        vec2 a = p - i + (i.x + i.y) * K2;
        vec2 o = (a.x > a.y) ? vec2(1.0, 0.0) : vec2(0.0, 1.0);
        vec2 b = a - o + K2;
        vec2 c = a - 1.0 + 2.0 * K2;
        vec3 h = max(0.5 - vec3(dot(a, a), dot(b, b), dot(c, c)), 0.0);
        vec3 n = h * h * h * h * vec3(dot(a, hash(i)), dot(b, hash(i + o)), dot(c, hash(i + 1.0)));
        return dot(n, vec3(70.0));
      }

      void main() {
        vec2 uv = (gl_FragCoord.xy - 0.5 * iResolution.xy) / min(iResolution.x, iResolution.y);
        float dist = length(uv);
        float angle = atan(uv.y, uv.x);

        float speed = 1.2;
        float stateIntensity = 0.2;
        float distortion = 0.0;

        if (uState == 1) { // listening
          speed = 2.0;
          stateIntensity = 0.35 + uAudioLevel * 0.45;
          distortion = sin(angle * 6.0 + iTime * 3.0) * (0.04 + uAudioLevel * 0.1);
        } else if (uState == 2) { // thinking
          speed = 4.5;
          stateIntensity = 0.5;
          distortion = sin(angle * 8.0 - iTime * 6.0) * 0.08 + cos(angle * 4.0 + iTime * 4.0) * 0.04;
        } else if (uState == 3) { // speaking
          speed = 3.0;
          stateIntensity = 0.6 + uAudioLevel * 0.6;
          distortion = sin(angle * 5.0 + iTime * 4.0) * (0.06 + uAudioLevel * 0.14) 
                     + cos(angle * 9.0 - iTime * 3.5) * (0.04 + uAudioLevel * 0.08);
        } else { // idle
          speed = 1.0;
          stateIntensity = 0.2;
          distortion = sin(angle * 4.0 + iTime * 1.5) * 0.03;
        }

        // Add animated noise ripples
        float n = noise(vec2(angle * 2.0 + iTime * speed * 0.5, dist * 6.0 - iTime * speed));
        float ringDist = dist + distortion + n * 0.04;

        // Core glow and ethereal halo
        float coreRadius = 0.22 + stateIntensity * 0.08;
        float coreGlow = smoothstep(coreRadius + 0.15, coreRadius - 0.05, ringDist);
        float outerHalo = smoothstep(0.48, coreRadius, ringDist);
        float pulse = 0.9 + 0.1 * sin(iTime * speed * 2.0);

        // Color shifting along radial angles
        vec3 colA = uColor;
        vec3 colB = vec3(
          clamp(uColor.r + uColorShift * 0.8, 0.0, 1.0),
          clamp(uColor.g - uColorShift * 0.4, 0.0, 1.0),
          clamp(uColor.b + uColorShift * 0.5, 0.0, 1.0)
        );
        vec3 colC = vec3(0.9, 0.95, 1.0); // Bright core highlight

        float shiftFactor = 0.5 + 0.5 * sin(angle * 2.0 + iTime * (speed * 0.5));
        vec3 auraColor = mix(colA, colB, shiftFactor);

        // Bright energetic nucleus
        float nucleus = smoothstep(coreRadius * 0.6, 0.0, dist);
        auraColor = mix(auraColor, colC, nucleus * 0.7);

        float alpha = (coreGlow * 0.9 + outerHalo * 0.4) * pulse * (0.6 + stateIntensity * 0.5);
        alpha = clamp(alpha, 0.0, 1.0);

        gl_FragColor = vec4(auraColor * alpha, alpha);
      }
    `;

    function createShader(glCtx, type, source) {
      const shader = glCtx.createShader(type);
      glCtx.shaderSource(shader, source);
      glCtx.compileShader(shader);
      if (!glCtx.getShaderParameter(shader, gl.COMPILE_STATUS)) {
        console.error('Shader compile error:', glCtx.getShaderInfoLog(shader));
        glCtx.deleteShader(shader);
        return null;
      }
      return shader;
    }

    const vertexShader = createShader(gl, gl.VERTEX_SHADER, vsSource);
    const fragmentShader = createShader(gl, gl.FRAGMENT_SHADER, fsSource);
    if (!vertexShader || !fragmentShader) return;

    const program = gl.createProgram();
    gl.attachShader(program, vertexShader);
    gl.attachShader(program, fragmentShader);
    gl.linkProgram(program);

    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
      console.error('Program link error:', gl.getProgramInfoLog(program));
      return;
    }

    gl.useProgram(program);

    // Full screen quad buffer
    const positionBuffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, positionBuffer);
    gl.bufferData(
      gl.ARRAY_BUFFER,
      new Float32Array([-1, -1, 1, -1, -1, 1, -1, 1, 1, -1, 1, 1]),
      gl.STATIC_DRAW
    );

    const aPosition = gl.getAttribLocation(program, 'aPosition');
    gl.enableVertexAttribArray(aPosition);
    gl.vertexAttribPointer(aPosition, 2, gl.FLOAT, false, 0, 0);

    // Uniform locations
    const uResolution = gl.getUniformLocation(program, 'iResolution');
    const uTime = gl.getUniformLocation(program, 'iTime');
    const uCol = gl.getUniformLocation(program, 'uColor');
    const uColShift = gl.getUniformLocation(program, 'uColorShift');
    const uAudLevel = gl.getUniformLocation(program, 'uAudioLevel');
    const uStateLoc = gl.getUniformLocation(program, 'uState');

    gl.enable(gl.BLEND);
    gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);

    let startTime = performance.now();

    const render = () => {
      const now = performance.now();
      const elapsed = (now - startTime) / 1000;

      // Handle resize / high-DPI
      const dpr = window.devicePixelRatio || 1;
      const displayWidth = Math.round(canvas.clientWidth * dpr);
      const displayHeight = Math.round(canvas.clientHeight * dpr);

      if (canvas.width !== displayWidth || canvas.height !== displayHeight) {
        canvas.width = displayWidth;
        canvas.height = displayHeight;
        gl.viewport(0, 0, displayWidth, displayHeight);
      }

      gl.clearColor(0, 0, 0, 0);
      gl.clear(gl.COLOR_BUFFER_BIT);

      gl.uniform2f(uResolution, canvas.width, canvas.height);
      gl.uniform1f(uTime, elapsed);
      gl.uniform3f(uCol, r, g, b);
      gl.uniform1f(uColShift, colorShift);
      gl.uniform1f(uAudLevel, audioLevelRef.current || 0.0);

      // State integer mapping
      const stateMap = { idle: 0, listening: 1, thinking: 2, speaking: 3 };
      gl.uniform1i(uStateLoc, stateMap[stateRef.current] ?? 0);

      gl.drawArrays(gl.TRIANGLES, 0, 6);

      animFrameRef.current = requestAnimationFrame(render);
    };

    animFrameRef.current = requestAnimationFrame(render);

    return () => {
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
      if (gl) {
        gl.deleteProgram(program);
        gl.deleteShader(vertexShader);
        gl.deleteShader(fragmentShader);
        gl.deleteBuffer(positionBuffer);
      }
    };
  }, [color, colorShift]);

  return (
    <div
      className={`relative flex items-center justify-center ${className}`}
      style={{
        width: pixelSize,
        height: pixelSize,
        maxWidth: '100%',
        margin: '0 auto',
        ...style,
      }}
    >
      <canvas
        ref={canvasRef}
        style={{
          width: '100%',
          height: '100%',
          display: 'block',
          borderRadius: '50%',
        }}
      />
    </div>
  );
}

// Re-export for standard naming
export default AgentAudioVisualizerAura;
