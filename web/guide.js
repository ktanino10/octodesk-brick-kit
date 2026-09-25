import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { STLLoader } from "three/addons/loaders/STLLoader.js";

const $ = (id) => document.getElementById(id);
const D = window.OCTODESK_DATA;
const K = D.kit;
const total = K.instances.length;
const instances = new Map(K.instances.map((i) => [i.id, i]));
const geometries = new Map();
const state = { count: 0, selected: null, plate: 0, slot: 1, explode: 0, playing: false, motion: null, stopAt: total };
const viewers = {};
let selectedOutline;
let animationHandle;

function fail(error) {
  stop();
  $("load-error").hidden = false;
  $("load-error").textContent = `3Dガイドを読み込めませんでした: ${error.message}。PDFとCSVは利用できます。`;
  console.error(error);
}

function makeGeometry(pid) {
  if (!geometries.has(pid)) {
    const raw = atob(D.meshes[pid]);
    const bytes = Uint8Array.from(raw, (c) => c.charCodeAt(0));
    const geometry = new STLLoader().parse(bytes.buffer);
    geometry.computeBoundingBox();
    geometries.set(pid, geometry);
  }
  return geometries.get(pid);
}

function material(color) {
  return new THREE.MeshStandardMaterial({ color: K.colors[color].hex, roughness: .56, metalness: 0 });
}

function createViewer(containerId, kind) {
  const element = $(containerId);
  const scene = new THREE.Scene();
  scene.background = new THREE.Color("#edf2ee");
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.6));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  element.append(renderer.domElement);
  const camera = new THREE.PerspectiveCamera(36, 1, .1, 5000);
  camera.up.set(0, 0, 1);
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.minDistance = 28;
  controls.maxDistance = 2200;
  scene.add(new THREE.HemisphereLight(0xffffff, 0x8b9a8f, 2.1));
  for (const [position, power] of [[[200, -280, 500], 2.4], [[350, 280, 260], 1.6]]) {
    const light = new THREE.DirectionalLight(0xffffff, power);
    light.position.set(...position);
    scene.add(light);
  }
  const group = new THREE.Group();
  scene.add(group);
  const grid = new THREE.GridHelper(kind === "plate" ? 256 : 240, kind === "plate" ? 16 : 30, 0xc0d1c6, 0xdde6df);
  grid.rotation.x = Math.PI / 2;
  grid.position.set(kind === "plate" ? 128 : 96, kind === "plate" ? 128 : 64, -.12);
  scene.add(grid);
  const viewer = { element, scene, camera, controls, renderer, group, kind, meshes: [], labels: [], view: "iso" };
  viewer.dirty = true;
  const observer = new ResizeObserver(() => {
    const width = element.clientWidth, height = element.clientHeight;
    renderer.setSize(width, height, false);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    fit(viewer);
  });
  observer.observe(element);
  viewer.observer = observer;
  let pointerDown;
  renderer.domElement.addEventListener("pointerdown", (e) => { pointerDown = [e.clientX, e.clientY]; });
  renderer.domElement.addEventListener("pointerup", (event) => {
    if (!pointerDown || Math.hypot(event.clientX - pointerDown[0], event.clientY - pointerDown[1]) > 6) return;
    const rect = renderer.domElement.getBoundingClientRect();
    const ndc = new THREE.Vector2((event.clientX - rect.left) / rect.width * 2 - 1, -(event.clientY - rect.top) / rect.height * 2 + 1);
    const ray = new THREE.Raycaster();
    ray.setFromCamera(ndc, camera);
    const hit = ray.intersectObjects(viewer.meshes.filter((m) => m.visible), false)[0];
    if (!hit) return;
    stop();
    if (kind === "plate") selectSlot(hit.object.userData.slot);
    else selectInstance(hit.object.userData.instance, false);
  });
  return viewer;
}

function viewerBounds(viewer) {
  if (viewer.kind === "plate" && !$("isolate-part").checked) return new THREE.Box3(new THREE.Vector3(0, 0, 0), new THREE.Vector3(256, 256, 16));
  const b = new THREE.Box3();
  viewer.group.updateMatrixWorld(true);
  for (const mesh of viewer.meshes) if (mesh.visible) b.union(mesh.geometry.boundingBox.clone().applyMatrix4(mesh.matrixWorld));
  if (b.isEmpty()) return new THREE.Box3(new THREE.Vector3(0, 0, 0), new THREE.Vector3(192, 128, 80));
  return b;
}

function fit(viewer, name = viewer.view) {
  viewer.view = name;
  const box = viewerBounds(viewer);
  const center = box.getCenter(new THREE.Vector3());
  const radius = box.getSize(new THREE.Vector3()).length() / 2;
  const vertical = THREE.MathUtils.degToRad(viewer.camera.fov / 2);
  const horizontal = Math.atan(Math.tan(vertical) * viewer.camera.aspect);
  const distance = Math.max(25, radius / Math.sin(Math.min(vertical, horizontal)) * 1.07);
  const directions = {
    iso: [1.1, -1.55, 1.0], front: [0, -1, .0001], right: [1, 0, .0001],
    left: [-1, 0, .0001], back: [0, 1, .0001], top: [0, -.0001, 1], bottom: [0, -.0001, -1]
  };
  viewer.camera.up.set(0, 0, 1);
  if (name === "top") viewer.camera.up.set(0, 1, 0);
  if (name === "bottom") viewer.camera.up.set(0, -1, 0);
  viewer.camera.position.copy(center).add(new THREE.Vector3(...directions[name]).normalize().multiplyScalar(distance));
  viewer.controls.target.copy(center);
  viewer.camera.near = .1;
  viewer.camera.far = Math.max(5000, distance * 3);
  viewer.camera.updateProjectionMatrix();
  viewer.camera.lookAt(center);
  viewer.controls.update();
  viewer.dirty = true;
}

function createAssembly() {
  const viewer = viewers.assembly;
  for (const inst of K.instances) {
    const mesh = new THREE.Mesh(makeGeometry(inst.part), material(inst.color));
    mesh.position.set(...inst.translation_mm);
    mesh.rotation.z = THREE.MathUtils.degToRad(inst.rotation_deg);
    mesh.userData = { instance: inst.id, ordinal: viewer.meshes.length };
    mesh.visible = false;
    viewer.group.add(mesh);
    viewer.meshes.push(mesh);
  }
  selectedOutline = new THREE.Box3Helper(new THREE.Box3(), 0xc35b2c);
  selectedOutline.visible = false;
  viewer.scene.add(selectedOutline);
}

function buildPlate() {
  const viewer = viewers.plate;
  for (const mesh of viewer.meshes) mesh.material.dispose();
  viewer.group.clear();
  viewer.labels.forEach((label) => label.element.remove());
  viewer.labels = [];
  viewer.meshes = [];
  const plate = D.manifest.plates[state.plate];
  $("plate-select").value = String(state.plate);
  $("slot-select").replaceChildren();
  for (const slot of plate.slots) {
    const option = document.createElement("option");
    option.value = String(slot.slot);
    option.textContent = String(slot.slot).padStart(2, "0");
    $("slot-select").append(option);
    const mesh = new THREE.Mesh(makeGeometry(slot.part), material(slot.color));
    mesh.position.set(...slot.translation_mm);
    mesh.userData.slot = slot.slot;
    viewer.group.add(mesh);
    viewer.meshes.push(mesh);
    const label = document.createElement("span");
    label.className = "slot-label";
    label.textContent = String(slot.slot);
    viewer.element.append(label);
    viewer.labels.push({ element: label, mesh, slot: slot.slot });
  }
  $("plate-count").textContent = `${plate.slots.length}個 / NOT_SLICED`;
  fit(viewer);
}

function updatePlateSelection() {
  const plate = D.manifest.plates[state.plate];
  const slot = plate.slots[state.slot - 1];
  $("slot-select").value = String(state.slot);
  for (const mesh of viewers.plate.meshes) {
    mesh.visible = !$("isolate-part").checked || mesh.userData.slot === state.slot;
    mesh.material.emissive.setHex(mesh.userData.slot === state.slot ? 0x3a1300 : 0);
  }
  $("slot-info").textContent = `${plate.file.split("/").at(-1)} / slot ${slot.slot}\n${slot.part} · ${K.colors[slot.color].name} / 同形同色 ${slot.candidate_instances.length}個`;
  $("candidates").replaceChildren();
  for (const id of slot.candidate_instances) {
    const inst = instances.get(id);
    const button = document.createElement("button");
    button.textContent = `${id} · 工程${inst.step}`;
    button.className = id === state.selected ? "active" : "";
    button.addEventListener("click", () => { stop(); selectInstance(id, true); });
    $("candidates").append(button);
  }
  viewers.plate.dirty = true;
}

function selectSlot(number) {
  state.slot = number;
  const slot = D.manifest.plates[state.plate].slots[number - 1];
  const id = slot.candidate_instances.includes(state.selected) ? state.selected : slot.candidate_instances[0];
  selectInstance(id, true, false);
  updatePlateSelection();
  fit(viewers.plate);
}

function selectInstance(id, reveal = false, changeSource = true) {
  const inst = instances.get(id);
  state.selected = id;
  if (reveal) state.count = Math.max(state.count, K.instances.indexOf(inst) + 1);
  if (changeSource) {
    const source = D.manifest.instance_sources[id][0];
    const index = D.manifest.plates.findIndex((p) => p.file === source.file);
    if (state.plate !== index) { state.plate = index; buildPlate(); }
    state.slot = source.slot;
  }
  updatePlateSelection();
  renderAssembly();
  updateInfo();
  if (reveal) fit(viewers.assembly);
}

function renderAssembly() {
  for (let index = 0; index < total; index++) {
    const inst = K.instances[index], mesh = viewers.assembly.meshes[index];
    mesh.position.set(...inst.translation_mm);
    mesh.position.z += (inst.step - 1) * 10 * state.explode;
    mesh.visible = index < state.count || state.motion?.index === index;
    const dim = $("dim-parts").checked && inst.id !== state.selected;
    mesh.material.transparent = dim;
    mesh.material.opacity = dim ? .24 : 1;
    mesh.material.depthWrite = !dim;
    mesh.material.emissive.setHex(inst.id === state.selected ? 0x1e1407 : 0);
  }
  if (state.motion) {
    const mesh = viewers.assembly.meshes[state.motion.index];
    mesh.position.z += 40 * (1 - state.motion.progress);
  }
  const selected = viewers.assembly.meshes.find((m) => m.userData.instance === state.selected);
  selectedOutline.visible = Boolean(selected?.visible);
  if (selectedOutline.visible) {
    selected.updateWorldMatrix(true, false);
    selectedOutline.box.copy(selected.geometry.boundingBox).applyMatrix4(selected.matrixWorld);
  }
  viewers.assembly.dirty = true;
}

function updateInfo() {
  $("assembly-count").textContent = `${state.count} / ${total}個`;
  $("progress").value = String(state.count);
  $("progress-label").textContent = `${state.count}/${total}`;
  $("explode-label").textContent = `${Math.round(state.explode * 100)}%`;
  $("previous").disabled = state.count === 0 && !state.motion;
  $("next").disabled = state.count === total;
  $("play").disabled = state.playing || state.count === total;
  $("pause").disabled = !state.playing && !state.motion;
  const inst = state.selected ? instances.get(state.selected) : null;
  $("step-select").value = inst ? String(inst.step) : state.count === total ? String(K.steps.length) : "0";
  $("source-list").replaceChildren();
  if (!inst) {
    $("instance-info").textContent = state.count === total
      ? `完成 / ${total}個・${K.steps.length}工程。部品をクリックすると取り出し元を表示します。`
      : "0個配置済み / 空の机です。\n「次の1個」で O-001 の取り付けを始めます。";
    $("step-note").textContent = state.count === total
      ? "現物の嵌合・保持力・転倒・耐久性は未評価です。"
      : "台座の手前は−Y。最初の6枚は机に並べ、上段で連結します。";
    return;
  }
  const step = K.steps[inst.step - 1];
  $("instance-info").textContent = `${inst.id} / ${inst.part} / ${K.colors[inst.color].name} / 工程${inst.step}\n${inst.role} · 下角(${inst.anchor_mm.map((v) => v.toFixed(1)).join(", ")}) mm · Z回転${inst.rotation_deg}° · 上から↓`;
  $("step-note").textContent = `${step.title}。${step.note}`;
  const byFile = new Map();
  for (const source of D.manifest.instance_sources[inst.id]) {
    if (!byFile.has(source.file)) byFile.set(source.file, []);
    byFile.get(source.file).push(source.slot);
  }
  for (const [file, slots] of byFile) {
    const row = document.createElement("div"); row.className = "source-row";
    const name = document.createElement("span"); name.textContent = file.split("/").at(-1); row.append(name);
    for (const number of slots) {
      const b = document.createElement("button"); b.className = "source-item"; b.textContent = `slot ${number}`;
      b.addEventListener("click", () => {
        stop();
        state.plate = D.manifest.plates.findIndex((p) => p.file === file);
        state.slot = number;
        buildPlate(); updatePlateSelection(); fit(viewers.plate);
      });
      row.append(b);
    }
    $("source-list").append(row);
  }
}

function stop() {
  state.playing = false;
  state.motion = null;
  state.stopAt = total;
  if (viewers.assembly) { renderAssembly(); updateInfo(); }
}

function reset() {
  stop();
  state.count = 0; state.selected = null; state.explode = 0; $("explode").value = "0";
  renderAssembly(); updateInfo(); updatePlateSelection(); fit(viewers.assembly);
}

function beginNext() {
  if (state.count >= total) { stop(); return; }
  state.explode = 0; $("explode").value = "0";
  const index = state.count;
  selectInstance(K.instances[index].id, false);
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  state.motion = { index, started: performance.now(), duration: reduced ? 1 : Number($("speed").value), progress: 0 };
  renderAssembly();
  fit(viewers.assembly);
  updateInfo();
}

function complete() {
  stop();
  state.count = total; state.selected = null; state.explode = 0; $("explode").value = "0";
  $("dim-parts").checked = false;
  renderAssembly(); updateInfo(); fit(viewers.assembly);
  $("instance-info").textContent = `完成 / ${total}個・${K.steps.length}工程。部品をクリックすると取り出し元を表示します。`;
  $("step-note").textContent = "現物の嵌合・保持力・転倒・耐久性は未評価です。";
}

function tick(now) {
  try {
    if (state.motion) {
      state.motion.progress = Math.min(1, (now - state.motion.started) / state.motion.duration);
      renderAssembly();
      if (state.motion.progress >= 1) {
        state.count++;
        state.motion = null;
        renderAssembly(); updateInfo();
        if (state.playing && state.count < state.stopAt) beginNext();
        else { state.playing = false; updateInfo(); }
      }
    }
    for (const viewer of Object.values(viewers)) {
      const moved = viewer.controls.update();
      if (!moved && !viewer.dirty) continue;
      viewer.renderer.render(viewer.scene, viewer.camera);
      viewer.dirty = false;
      for (const label of viewer.labels) {
        const point = label.mesh.geometry.boundingBox.getCenter(new THREE.Vector3());
        point.z = label.mesh.geometry.boundingBox.max.z + 2;
        label.mesh.localToWorld(point); point.project(viewer.camera);
        label.element.hidden = !label.mesh.visible || Math.abs(point.x) > 1 || Math.abs(point.y) > 1 || point.z > 1;
        label.element.style.left = `${(point.x + 1) * .5 * viewer.element.clientWidth}px`;
        label.element.style.top = `${(1 - point.y) * .5 * viewer.element.clientHeight}px`;
        label.element.classList.toggle("selected", label.slot === state.slot);
      }
    }
    animationHandle = requestAnimationFrame(tick);
  } catch (error) { fail(error); }
}

function init() {
  $("metrics").innerHTML = `<div><b>${D.catalog.assembly_size_mm.map((n) => Number(n.toFixed(1))).join(" × ")}</b><small>完成寸法 mm（スタッド・耳を含む）</small></div><div><b>${total}</b><small>個 / ${K.counts.assembly_types}型</small></div><div><b>${K.steps.length}</b><small>工程 / ${K.counts.colors}色</small></div>`;
  D.manifest.plates.forEach((plate, index) => {
    const option = document.createElement("option"); option.value = String(index);
    option.textContent = `${plate.file.split("/").at(-1)} (${plate.slots.length}個)`; $("plate-select").append(option);
    const link = document.createElement("a"); link.href = plate.file; link.textContent = option.textContent; link.download = "";
    $("plate-downloads").append(link);
  });
  $("step-select").append(new Option("0 · 空の机", "0"));
  for (const step of K.steps) $("step-select").append(new Option(`${step.number} · ${step.title}`, String(step.number)));
  for (const row of K.bom) {
    const tr = document.createElement("tr");
    const a = document.createElement("a"); a.href = D.catalog.parts[row.part].stl; a.textContent = row.part;
    const type = document.createElement("td"); type.append(a);
    const color = document.createElement("td");
    const swatch = document.createElement("span"); swatch.className = "swatch"; swatch.style.backgroundColor = K.colors[row.color].hex;
    color.append(swatch, K.colors[row.color].name);
    const count = document.createElement("td"); count.textContent = String(row.quantity);
    tr.append(type, color, count); $("bom").querySelector("tbody").append(tr);
  }
  $("progress").max = String(total);
  viewers.plate = createViewer("plate-viewport", "plate");
  viewers.assembly = createViewer("assembly-viewport", "assembly");
  createAssembly(); buildPlate(); updatePlateSelection(); renderAssembly(); updateInfo();
  fit(viewers.assembly); fit(viewers.plate);
  $("plate-select").addEventListener("change", () => {
    stop(); state.plate = Number($("plate-select").value); state.slot = 1; buildPlate(); selectSlot(1);
  });
  $("slot-select").addEventListener("change", () => { stop(); selectSlot(Number($("slot-select").value)); });
  $("isolate-part").addEventListener("change", () => { updatePlateSelection(); fit(viewers.plate); });
  $("dim-parts").addEventListener("change", renderAssembly);
  for (const row of document.querySelectorAll(".views")) {
    for (const button of row.querySelectorAll("button[data-view]")) button.addEventListener("click", () => fit(viewers[row.dataset.viewer], button.dataset.view));
  }
  $("reset").addEventListener("click", reset);
  $("pause").addEventListener("click", stop);
  $("next").addEventListener("click", () => { stop(); beginNext(); });
  $("play").addEventListener("click", () => { state.playing = true; state.stopAt = total; if (!state.motion) beginNext(); });
  $("previous").addEventListener("click", () => {
    stop(); state.count = Math.max(0, state.count - 1); state.selected = state.count ? K.instances[state.count - 1].id : null;
    if (state.selected) selectInstance(state.selected); else { renderAssembly(); updateInfo(); }
    fit(viewers.assembly);
  });
  $("complete").addEventListener("click", complete);
  $("progress").addEventListener("input", () => {
    const count = Number($("progress").value);
    stop(); state.count = count; state.selected = state.count ? K.instances[state.count - 1].id : null;
    if (state.selected) selectInstance(state.selected); else { renderAssembly(); updateInfo(); }
    fit(viewers.assembly);
  });
  $("explode").addEventListener("input", () => {
    stop(); state.count = total; state.explode = Number($("explode").value) / 100;
    renderAssembly(); updateInfo(); fit(viewers.assembly);
  });
  $("step-select").addEventListener("change", () => {
    const step = Number($("step-select").value);
    stop();
    if (!step) { reset(); return; }
    state.count = K.instances.findLastIndex((i) => i.step === step) + 1;
    selectInstance(K.instances[state.count - 1].id); fit(viewers.assembly);
  });
  $("replay-step").addEventListener("click", () => {
    stop(); const number = Number($("step-select").value) || 1;
    state.count = K.instances.findIndex((i) => i.step === number);
    state.playing = true;
    state.stopAt = K.instances.findLastIndex((i) => i.step === number) + 1;
    beginNext();
  });
  document.addEventListener("visibilitychange", () => { if (document.hidden) stop(); });
  window.OCTODESK_APP = {
    ready: true, getState: () => ({ ...state, motion: state.motion ? { ...state.motion } : null }),
    getTransforms: () => viewers.assembly.meshes.map((m) => ({ id: m.userData.instance, visible: m.visible, position: m.position.toArray(), rotationZ: m.rotation.z })),
    projectedBounds: () => {
      const v = viewers.assembly, b = viewerBounds(v); v.camera.updateMatrixWorld();
      return [b.min.x, b.max.x].flatMap((x) => [b.min.y, b.max.y].flatMap((y) =>
        [b.min.z, b.max.z].map((z) => new THREE.Vector3(x, y, z).project(v.camera).toArray())));
    },
    sourceCount: (id) => D.manifest.instance_sources[id].length
  };
  const requested = new URLSearchParams(location.search).get("part");
  if (requested && instances.has(requested)) selectInstance(requested, true);
  animationHandle = requestAnimationFrame(tick);
}

window.addEventListener("pagehide", () => { stop(); cancelAnimationFrame(animationHandle); });
try { init(); } catch (error) { fail(error); }
