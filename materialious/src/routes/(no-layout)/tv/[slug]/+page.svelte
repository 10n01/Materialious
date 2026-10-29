<script lang="ts">
	import Player from '#lib/components/player/Player.svelte';
	import { letterCase } from '#lib/letterCasing';
	import Mousetrap from 'mousetrap';
	import { onDestroy, onMount, tick } from 'svelte';
	import { _ } from '#lib/i18n/index';
	import { playlistCacheStore, activeCaptionTrack } from '#lib/store';
	import { toggleSubtitles } from '#lib/player/index';
	import { fade } from 'svelte/transition';
	import { goto } from '$app/navigation';
	import { resolveWatchPath } from '#lib/paths';
	import { imageHandleCors, getBestLandscapeThumbnail } from '#lib/images';
	import { videoLength } from '#lib/numbers';
	import { getNextFocus } from '@bbc/tv-lrud-spatial';
	import { keyCodeMap } from '#lib/utils';

	let { data } = $props();

	let playerElement: HTMLMediaElement | undefined = $state();
	let showInfo = $state(false);
	let infoPanel: HTMLElement | undefined = $state();
	let playerCurrentTime: number = $state(0);
	let showControls = $state(false);
	let currentTime = $state(0);
	let userManualSeeking = $state(false);
	let currentSpeed = $state(1.0);

	let autoHideTimer: ReturnType<typeof setTimeout> | null = null;
	let seekRaf: number | null = null;
	let seekStartTime = 0;
	let isSeeking = false;
	let lastUpdate = 0;

	const hasChapters = $derived(data.content.timestamps.length > 0);
	const hasPlaylist = $derived(!!data.playlistId && data.playlistId in $playlistCacheStore);
	const recommendedList = $derived(data.video.recommendedVideos ?? []);
	const hasRecommended = $derived(recommendedList.length > 0);
	const speeds = [0.75, 1.0, 1.25, 1.5, 2.0];

	function resetAutoHideTimer() {
		if (autoHideTimer) clearTimeout(autoHideTimer);
		if (showInfo) {
			autoHideTimer = setTimeout(() => {
				closeInfo();
			}, 7000);
		}
	}

	function openInfo() {
		showInfo = true;
		resetAutoHideTimer();
		if (playerElement) currentSpeed = playerElement.playbackRate || 1.0;

		tick().then(() => {
			const focusTarget = infoPanel?.querySelector<HTMLElement>(
				'.rec-card, .tv-speed-chip, .tv-action-chip'
			);
			if (focusTarget) {
				focusTarget.focus();
				focusTarget.scrollIntoView({ block: 'nearest', inline: 'nearest' });
			}
		});
	}

	function closeInfo() {
		if (autoHideTimer) clearTimeout(autoHideTimer);
		showInfo = false;
		(document.activeElement as HTMLElement | null)?.blur();
	}

	function setSpeed(speed: number) {
		if (playerElement) {
			playerElement.playbackRate = speed;
			currentSpeed = speed;
		}
		resetAutoHideTimer();
	}

	function handleToggleCC() {
		toggleSubtitles();
		resetAutoHideTimer();
	}

	function goToRecommended(videoId: string) {
		closeInfo();
		goto(resolveWatchPath(videoId), { replace: true });
	}

	function activateChapter(timestamp: { time: number }) {
		if (playerElement) playerElement.currentTime = timestamp.time;
		closeInfo();
	}

	function startSeeking(direction: 'left' | 'right') {
		showControls = true;

		if (!playerElement || showInfo || isSeeking) return true;

		userManualSeeking = true;
		isSeeking = true;
		lastUpdate = performance.now();

		const duration = data.video.lengthSeconds;
		const base = duration * 0.005;

		function step(now: number) {
			if (!isSeeking) return;

			const elapsedTotal = (now - seekStartTime) / 1000;
			const throttleDelta = now - lastUpdate;

			if (throttleDelta > 100) {
				const factor = 1 + Math.min(elapsedTotal ** 1.2, 3);
				const amount = base * factor;

				if (direction === 'right') {
					currentTime = Math.min(currentTime + amount, duration);
				} else {
					currentTime = Math.max(currentTime - amount, 0);
				}

				lastUpdate = now;
			}

			seekRaf = requestAnimationFrame(step);
		}

		seekStartTime = performance.now();
		seekRaf = requestAnimationFrame(step);

		return false;
	}

	function stopSeeking() {
		isSeeking = false;
		showControls = false;
		userManualSeeking = false;

		if (seekRaf !== null) {
			cancelAnimationFrame(seekRaf);
			seekRaf = null;
		}

		if (playerElement && !showInfo) {
			playerElement.currentTime = currentTime;
		}
	}

	function handleInfoKeyDown(event: KeyboardEvent) {
		resetAutoHideTimer();

		if (event.key === 'Escape') {
			event.preventDefault();
			closeInfo();
			return;
		}

		const keyCode = keyCodeMap[event.key];
		if (!keyCode || !infoPanel) return;

		if (
			event.key === 'ArrowUp' ||
			event.key === 'ArrowDown' ||
			event.key === 'ArrowLeft' ||
			event.key === 'ArrowRight'
		) {
			const activeEl = document.activeElement as Element | null;
			if (activeEl) {
				const nextFocus = getNextFocus(activeEl, keyCode, infoPanel);
				if (nextFocus) {
					event.preventDefault();
					(nextFocus as HTMLElement).focus();
					(nextFocus as HTMLElement).scrollIntoView({
						block: 'nearest',
						inline: 'center',
						behavior: 'smooth'
					});
					return;
				}
			}

			if (event.key === 'ArrowUp') {
				event.preventDefault();
				closeInfo();
				return;
			}
		}
	}

	onMount(() => {
		if (playerElement) {
			playerElement.addEventListener('timeupdate', () => {
				if (!playerElement) return;
				playerCurrentTime = playerElement.currentTime;
			});
			currentSpeed = playerElement.playbackRate || 1.0;
		}

		Mousetrap.bind(
			'down',
			() => {
				if (showInfo) return true;
				openInfo();
				return false;
			},
			'keyup'
		);

		Mousetrap.bind(
			'up',
			() => {
				if (!showInfo) {
					openInfo();
					return false;
				}
				return true;
			},
			'keyup'
		);

		Mousetrap.bind('right', () => startSeeking('right'), 'keydown');
		Mousetrap.bind('right', stopSeeking, 'keyup');
		Mousetrap.bind('left', () => startSeeking('left'), 'keydown');
		Mousetrap.bind('left', stopSeeking, 'keyup');

		Mousetrap.bind(
			'esc',
			() => {
				if (showInfo) {
					closeInfo();
					return false;
				}
				return true;
			},
			'keyup'
		);

		Mousetrap.bind(
			'enter',
			() => {
				if (!showInfo) {
					if (playerElement?.paused) {
						showControls = false;
						playerElement?.play();
					} else {
						showControls = true;
						playerElement?.pause();
					}
					return false;
				}
				return true;
			},
			'keyup'
		);
	});

	onDestroy(() => {
		if (autoHideTimer) clearTimeout(autoHideTimer);
		Mousetrap.unbind(['up', 'down', 'left', 'right', 'enter', 'esc']);
	});
</script>

{#key data.video.videoId}
	<Player
		bind:playerElement
		bind:currentTime
		bind:userManualSeeking
		isEmbed={true}
		{data}
		{showControls}
	/>
{/key}

{#if showInfo}
	<article
		id="shown-info"
		transition:fade={{ duration: 180 }}
		bind:this={infoPanel}
		onkeydown={handleInfoKeyDown}
		role="dialog"
		aria-label={data.video.title}
	>
		<!-- Top Controls & Video Header -->
		<div class="tv-drawer-header">
			<div class="tv-header-info">
				<h5 class="tv-video-title">{letterCase(data.video.title)}</h5>
				<p class="tv-video-author">{data.video.author}</p>
			</div>

			<div class="tv-actions-row">
				<!-- CC Toggle -->
				<button
					type="button"
					class="tv-action-chip"
					class:active={$activeCaptionTrack !== null}
					onclick={handleToggleCC}
					aria-label="Bật hoặc tắt phụ đề"
				>
					<i>{$activeCaptionTrack !== null ? 'closed_caption' : 'closed_caption_disabled'}</i>
					<span>CC: {$activeCaptionTrack !== null ? 'Bật' : 'Tắt'}</span>
				</button>

				<!-- Playback Speed -->
				<div class="tv-speed-group">
					<span class="tv-speed-label">Tốc độ:</span>
					{#each speeds as s (s)}
						<button
							type="button"
							class="tv-speed-chip"
							class:active={Math.abs(currentSpeed - s) < 0.05}
							onclick={() => setSpeed(s)}
						>
							{s}x
						</button>
					{/each}
				</div>

				<!-- Close Button -->
				<button
					type="button"
					class="circle tv-action-chip tv-close-btn"
					aria-label={$_('player.closePlayer')}
					onclick={closeInfo}
				>
					<i>close</i>
				</button>
			</div>
		</div>

		<!-- Horizontal Shelves Area -->
		<div class="tv-drawer-body">
			<!-- Chapters Shelf -->
			{#if hasChapters}
				<div class="tv-shelf-section">
					<h6 class="tv-shelf-title">{$_('player.chapters')}</h6>
					<div class="tv-shelf-row">
						{#each data.content.timestamps as timestamp, index (timestamp)}
							{@const isCurrent =
								playerCurrentTime >= timestamp.time &&
								(playerCurrentTime <= timestamp.endTime || timestamp.endTime === -1)}
							<button
								type="button"
								class="tv-chapter-chip"
								class:active={isCurrent}
								onclick={() => activateChapter(timestamp)}
							>
								<span class="tv-chapter-time">{timestamp.timePretty}</span>
								<span class="tv-chapter-name">{timestamp.title}</span>
							</button>
						{/each}
					</div>
				</div>
			{/if}

			<!-- Recommended Videos Shelf -->
			{#if hasRecommended}
				<div class="tv-shelf-section">
					<h6 class="tv-shelf-title">{$_('recommendedVideos')}</h6>
					<div class="tv-shelf-row">
						{#each recommendedList as rec (rec.videoId)}
							{@const thumbUrl = imageHandleCors(
								getBestLandscapeThumbnail(rec.videoThumbnails)
							)}
							<button
								type="button"
								class="rec-card"
								onclick={() => goToRecommended(rec.videoId)}
							>
								<div class="rec-thumb-wrap">
									{#if thumbUrl}
										<img src={thumbUrl} alt={rec.title} loading="lazy" />
									{:else}
										<div class="rec-thumb-placeholder"><i>play_arrow</i></div>
									{/if}
									{#if rec.lengthSeconds}
										<span class="rec-badge">{videoLength(rec.lengthSeconds)}</span>
									{/if}
								</div>
								<div class="rec-card-info">
									<p class="rec-card-title">{rec.title}</p>
									<p class="rec-card-meta">{rec.author}</p>
								</div>
							</button>
						{/each}
					</div>
				</div>
			{/if}

			<!-- Playlist Videos Shelf -->
			{#if hasPlaylist}
				<div class="tv-shelf-section">
					<h6 class="tv-shelf-title">{$_('playlistVideos')}</h6>
					<div class="tv-shelf-row">
						{#each $playlistCacheStore[data.playlistId!].videos as plVideo (plVideo.videoId)}
							{@const thumbUrl = imageHandleCors(
								getBestLandscapeThumbnail(plVideo.videoThumbnails)
							)}
							<button
								type="button"
								class="rec-card"
								class:active={plVideo.videoId === data.video.videoId}
								onclick={() => goToRecommended(plVideo.videoId)}
							>
								<div class="rec-thumb-wrap">
									{#if thumbUrl}
										<img src={thumbUrl} alt={plVideo.title} loading="lazy" />
									{:else}
										<div class="rec-thumb-placeholder"><i>play_arrow</i></div>
									{/if}
									{#if plVideo.lengthSeconds}
										<span class="rec-badge">{videoLength(plVideo.lengthSeconds)}</span>
									{/if}
								</div>
								<div class="rec-card-info">
									<p class="rec-card-title">{plVideo.title}</p>
									<p class="rec-card-meta">{plVideo.author}</p>
								</div>
							</button>
						{/each}
					</div>
				</div>
			{/if}
		</div>
	</article>
{/if}

<style>
	#shown-info {
		position: fixed;
		bottom: 0;
		left: 0;
		width: 100%;
		max-height: 44%;
		z-index: 101;
		display: flex;
		flex-direction: column;
		background: rgba(14, 14, 18, 0.94);
		backdrop-filter: blur(24px);
		-webkit-backdrop-filter: blur(24px);
		border-top: 1px solid rgba(255, 255, 255, 0.16);
		box-shadow: 0 -16px 48px rgba(0, 0, 0, 0.9);
		border-top-left-radius: 20px;
		border-top-right-radius: 20px;
		padding: 0.8rem 1.5rem 1rem 1.5rem;
		box-sizing: border-box;
		color: #fff;
	}

	.tv-drawer-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 1.5rem;
		padding-bottom: 0.6rem;
		border-bottom: 1px solid rgba(255, 255, 255, 0.12);
		flex-shrink: 0;
	}

	.tv-header-info {
		flex: 1;
		min-width: 0;
	}

	.tv-video-title {
		margin: 0;
		font-size: 1.1rem;
		font-weight: 700;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
		color: #fff;
	}

	.tv-video-author {
		margin: 0.2rem 0 0 0;
		font-size: 0.85rem;
		opacity: 0.75;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
		color: rgba(255, 255, 255, 0.8);
	}

	.tv-actions-row {
		display: flex;
		align-items: center;
		gap: 0.8rem;
		flex-shrink: 0;
	}

	.tv-action-chip {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		padding: 0.4rem 0.9rem;
		border-radius: 9999px;
		border: 2px solid transparent;
		background: rgba(255, 255, 255, 0.12);
		color: #fff;
		font-size: 0.85rem;
		font-weight: 500;
		cursor: pointer;
		transition: all 0.15s ease;
	}

	.tv-action-chip.active {
		background: var(--primary, #90caf9);
		color: #000;
		font-weight: 700;
	}

	.tv-action-chip:focus {
		outline: none;
		border-color: #fff;
		transform: scale(1.08);
		box-shadow: 0 0 14px rgba(255, 255, 255, 0.7);
	}

	.tv-speed-group {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
		background: rgba(255, 255, 255, 0.08);
		padding: 0.2rem 0.5rem;
		border-radius: 9999px;
	}

	.tv-speed-label {
		font-size: 0.8rem;
		opacity: 0.75;
		margin-right: 0.25rem;
		color: #fff;
	}

	.tv-speed-chip {
		padding: 0.3rem 0.6rem;
		border-radius: 9999px;
		border: 2px solid transparent;
		background: transparent;
		color: #fff;
		font-size: 0.8rem;
		font-weight: 500;
		cursor: pointer;
		transition: all 0.15s ease;
	}

	.tv-speed-chip.active {
		background: rgba(255, 255, 255, 0.28);
		font-weight: 700;
	}

	.tv-speed-chip:focus {
		outline: none;
		border-color: #fff;
		background: var(--primary, #90caf9);
		color: #000;
		transform: scale(1.15);
		box-shadow: 0 0 14px rgba(255, 255, 255, 0.7);
	}

	.tv-close-btn {
		width: 2.2rem;
		height: 2.2rem;
		padding: 0;
		display: inline-flex;
		align-items: center;
		justify-content: center;
	}

	.tv-drawer-body {
		flex: 1;
		min-height: 0;
		overflow-y: auto;
		overflow-x: hidden;
		padding-top: 0.6rem;
		display: flex;
		flex-direction: column;
		gap: 0.8rem;
	}

	.tv-shelf-section {
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
	}

	.tv-shelf-title {
		margin: 0;
		font-size: 0.85rem;
		font-weight: 600;
		opacity: 0.85;
		text-transform: uppercase;
		letter-spacing: 0.6px;
		color: rgba(255, 255, 255, 0.9);
	}

	.tv-shelf-row {
		display: flex;
		gap: 1.1rem;
		overflow-x: auto;
		overflow-y: hidden;
		padding: 0.4rem 0.3rem 0.8rem 0.3rem;
		scroll-behavior: smooth;
	}

	.tv-chapter-chip {
		display: inline-flex;
		flex-direction: column;
		align-items: flex-start;
		padding: 0.45rem 0.9rem;
		border-radius: 10px;
		border: 2px solid transparent;
		background: rgba(255, 255, 255, 0.1);
		color: #fff;
		white-space: nowrap;
		cursor: pointer;
		transition: all 0.15s ease;
		flex-shrink: 0;
	}

	.tv-chapter-chip.active {
		background: var(--primary-container, #1e3a5f);
		border-color: var(--primary, #90caf9);
	}

	.tv-chapter-chip:focus {
		outline: none;
		border-color: #fff;
		transform: scale(1.06);
		box-shadow: 0 0 14px rgba(255, 255, 255, 0.6);
	}

	.tv-chapter-time {
		font-size: 0.72rem;
		opacity: 0.75;
	}

	.tv-chapter-name {
		font-size: 0.82rem;
		font-weight: 600;
	}

	.rec-card {
		width: 220px;
		min-width: 220px;
		max-width: 220px;
		border-radius: 12px;
		border: 2px solid transparent;
		background: rgba(255, 255, 255, 0.08);
		color: #fff;
		padding: 0;
		text-align: left;
		cursor: pointer;
		display: flex;
		flex-direction: column;
		overflow: hidden;
		transition: transform 0.15s ease, border-color 0.15s ease, box-shadow 0.15s ease;
		flex-shrink: 0;
	}

	.rec-card.active {
		border-color: var(--primary, #90caf9);
	}

	.rec-card:focus {
		outline: none;
		border-color: #fff;
		transform: scale(1.07);
		box-shadow: 0 0 18px rgba(255, 255, 255, 0.7);
		background: rgba(255, 255, 255, 0.18);
		z-index: 10;
	}

	.rec-thumb-wrap {
		position: relative;
		width: 100%;
		aspect-ratio: 16 / 9;
		background: #111;
		overflow: hidden;
	}

	.rec-thumb-wrap img {
		width: 100%;
		height: 100%;
		object-fit: cover;
		display: block;
	}

	.rec-thumb-placeholder {
		width: 100%;
		height: 100%;
		display: flex;
		align-items: center;
		justify-content: center;
		color: rgba(255, 255, 255, 0.4);
	}

	.rec-badge {
		position: absolute;
		bottom: 5px;
		right: 5px;
		background: rgba(0, 0, 0, 0.85);
		color: #fff;
		font-size: 0.72rem;
		font-weight: 600;
		padding: 2px 6px;
		border-radius: 4px;
	}

	.rec-card-info {
		padding: 0.5rem 0.6rem;
		display: flex;
		flex-direction: column;
		gap: 0.2rem;
	}

	.rec-card-title {
		margin: 0;
		font-size: 0.82rem;
		font-weight: 600;
		line-height: 1.25;
		display: -webkit-box;
		-webkit-line-clamp: 2;
		-webkit-box-orient: vertical;
		overflow: hidden;
		color: #fff;
	}

	.rec-card-meta {
		margin: 0;
		font-size: 0.72rem;
		opacity: 0.75;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
		color: rgba(255, 255, 255, 0.8);
	}
</style>
