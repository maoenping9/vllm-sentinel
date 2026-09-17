#!/usr/bin/env osascript -l JavaScript
// vLLM HUD — native always-on-top floating window (JXA ObjC bridge)
ObjC.import('Cocoa');
ObjC.import('WebKit');

const APP = $.NSApplication.sharedApplication;
APP.setActivationPolicy($.NSApplicationActivationPolicyAccessory);

// geometry (screen coords, y from bottom)
const X = 1180, Y = 560, W = 330, H = 420;
const rect = $.NSMakeRect(X, Y, W, H);

// NSPanel: borderless + nonactivating (raw mask 1<<7 = nonactivatingPanel)
const STYLE_NONACTIVATING = 1 << 7;
const panel = $.NSPanel.alloc.initWithContentRectStyleMaskBackingDefer(
  rect, STYLE_NONACTIVATING, $.NSBackingStoreBuffered, false
);
panel.setLevel($.NSFloatingWindowLevel);          // above normal windows
panel.setCollectionBehavior(1 | (1 << 8));        // join all spaces + fullscreen auxiliary
panel.setOpaque(false);
panel.setBackgroundColor($.NSColor.clearColor);
panel.setHasShadow(true);
panel.setIgnoresMouseEvents(false);
panel.setHidesOnDeactivate(false);

// webview: addSubview FIRST, then load (wrong order = blank webview)
const web = $.WKWebView.alloc.initWithFrame($.NSMakeRect(0, 0, W, H));
panel.contentView.addSubview(web);
const url = $.NSURL.fileURLWithPath('/Users/maoenping/Desktop/vllm-monitor/vllm-monitor.html');
const dir = $.NSURL.fileURLWithPath('/Users/maoenping/Desktop/vllm-monitor/');
const nav = web.loadFileURLAllowingReadAccessToURL(url, dir);
console.log('loadFileURL:', nav ? 'ok' : 'NIL');
panel.orderFront($());

// enter the real Cocoa event loop — WKWebView composites continuously,
// page JS refreshes steadily, and the panel stays ordered front.
$.NSRunLoop.mainRunLoop.run();
